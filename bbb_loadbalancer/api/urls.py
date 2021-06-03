from django.urls import path

from api.views import *


urlpatterns = [
    path("create", Create.as_view()),
    path("join", Join.as_view()),
    path("isMeetingRunning", IsMeetingRunning.as_view()),
    path("end", End.as_view()),
    path("getMeetingInfo", GetMeetingInfo.as_view()),
    path("getMeetings", GetMeetings.as_view()),
    path("getRecordings", GetRecordings.as_view()),
    path("publishRecordings", PublishRecordings.as_view()),
    path("deleteRecordings", DeleteRecordings.as_view()),
    path("updateRecordings", UpdateRecordings.as_view()),
    path("getDefaultConfigXML", GetDefaultConfigXML.as_view()),
    path("getRecordingTextTracks", GetRecordingTextTracks.as_view()),
    path("putRecordingTestTracks", PutRecordingTestTracks.as_view()),
    path("move", Move.as_view()),
    path("getStatistics", GetStatistics.as_view()),
    path('', DefaultView.as_view()),
]

