from rest_framework.mixins import RetrieveModelMixin
from groups.models import Membership
from groups.methods import get_memberships
from authentication.middleware import check_requester_is_authenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from authentication.models import User
from groups.models import Group
from .models import Event, Slot, Tag
from .methods import create_event, event_to_json
from authentication.middleware import check_requester_is_authenticated
from groups.middleware import check_group_exists, check_requester_is_group_admin
from common.parsers import parse_epoch_timestamp_to_datetime
from rest_framework.permissions import (
    IsAuthenticated,
    BasePermission,
)
from .serializers import PostEventSerializer, EventSerializer

class EventPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100

# Create your views here.
class GroupEventsView(APIView):
    @check_requester_is_authenticated
    @check_group_exists
    @check_requester_is_group_admin
    def post(self, request, requester: User, group: Group):
        serializer = PostEventSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Create but don't save event first
        start_date_time = validated_data.get('start_date_time')
        end_date_time = validated_data.get('end_date_time')

        new_event = Event(
            title=validated_data.get('title', ''),
            description=validated_data.get('description', ''),
            group=group,
            start_date_time=parse_epoch_timestamp_to_datetime(start_date_time),
            end_date_time=parse_epoch_timestamp_to_datetime(end_date_time),
            location=validated_data.get('location', ''),
            is_public=validated_data.get('is_public')
        )

        print(new_event)

        new_event.save()

        slots = validated_data.get('slots')
        for tag_name, limit in slots.items():
            new_slot = Slot(
                event=new_event,
                limit=limit,
                tag=Tag.objects.get(name=tag_name)
            )
            new_slot.save()

        return Response(event_to_json(new_event), status=status.HTTP_201_CREATED)

class EventListView(ListAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_class = EventPagination
    filter_backends = (DjangoFilterBackend, SearchFilter)
    filter_fields = ('id','group','is_public')
    search_fields = ('title', 'description')

class EventGroupAdminPermission(BasePermission):
    def has_permission(self, request, view):
        group = view.get_object().group
        try:
            membership = get_memberships(group=group, user=request.user).get()
            return membership.is_approved and membership.is_admin
        except (Membership.DoesNotExist):
            return False

class EventRetrieveView(RetrieveModelMixin, APIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def get(self, request, pk):
        event = self.get_object()
        return Response(event_to_json(event))
class EventRetrieveUpdateDestroy(RetrieveUpdateDestroyAPIView):
    lookup_field = 'id'
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated & EventGroupAdminPermission]

