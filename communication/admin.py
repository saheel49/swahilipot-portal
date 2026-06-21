from django.contrib import admin
from .models import Announcement, ChannelMessage, DepartmentChannel, DirectMessage, Notification

admin.site.register(Announcement)
admin.site.register(DepartmentChannel)
admin.site.register(ChannelMessage)
admin.site.register(DirectMessage)
admin.site.register(Notification)

