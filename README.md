# BBB Load balancer

This project is an alternative for bigbluebutton's scalelite.
It consists of three compontents:
  - a django server providing the web api
  - a poller service which checks the bigbluebutton servers in the cluster and if a meeting has been closed
  - a cli to add new bigbluebutton server and set one to panic

## API

We tried to emulate a bigbluebutton server's api as close as possible.

For a full documentation please use [bigbluebutton's offical docs](https://docs.bigbluebutton.org/dev/api.html).

## Tweaked Endpoints

### create

The **create** endpoint accepts a new optional parameter:

Param Name | Required / Optional | Type   | Description
-----------|---------------------|--------|----------------
load       | Optional            | Number | An abstract measure of how expensive the meeting is expected to get. <br> When determining on which server to create a new meeting the loadbalancer sums the load values of all running meetings for each server and chooses the one with the lowest total load. <br> Should be positive and defaults to 1 when not specified.

## Custom Endpoints

### move

Ends the meeting on its current server and tries to reopen it on another one.

If possible users will be redirected automaticly after pressing "ok" in their notifiaction window. This is based on a cookie which stores the last used join link. If the automatic process fails, users will have to join again using their inital join links.

Param Name | Required / Optional | Type   | Description
-----------|---------------------|--------|----------------
meetingID  | Required            | String | The meeting ID that identifies the meeting you want to move.
serverID   | Optional            | Number | Allows you to specify the server you want to move the meeting to. If not specified, it will choose one. <br> Each server is given an id by an administrator when added via the cli.

On success this endpoint has the same response as **create**.

### getStatistics

This endpoint requires no parameters and returns a list of all servers with all their running meetings.

It is very similar to **getMeetings**, but it lists each meeting under the server it runs on and doesn't output all attributes of a meeting.

Returned meeting attributes:
  - meetingID
  - participantCount
  - listenerCount
  - voiceParticipantCount
  - videoCount

Example Response:
```xml
<response>
  <returncode>SUCCESS</returncode>
  <servers>
    <server>
      <serverID>0</serverID>
      <meetings>
        <meeting>
          <meetingID>Demo Meeting</meetingID>
          <participantCount>2</participantCount>
          <listenerCount>1</listenerCount>
          <voiceParticipantCount>1</voiceParticipantCount>
          <videoCount>1</videoCount>
        </meeting>
        ...
      </meetings>
    </server>
    <server>
      <serverID>1</serverID>
      <meetings>...</meetings>
    </server>
    ...
  </servers>
</response>
```

### rejoin

An internal endpoint used to redirect users to a moved meeting.

Param Name | Required / Optional | Type   | Description
-----------|---------------------|--------|-------------
meetingID  | Required            | Number | **Attention! This is not the meeting id used in every other api endpoint!** <br> An internal id used only be the loadbalancer to uniquely identify any meeting in all meetings ever created. <br> Currently it is simply django's private key.

## Not Yet Implemented Endpoints

- **getDefaultConfigXML**
- **setConfigXMLAnchor**
- **getRecordingTextTracksAnchor**
- **putRecordingTextTrackAnchor**
