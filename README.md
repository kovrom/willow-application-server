# Willow Application Server

## This fork contains tweaks and modifications that may or may not be compatible with official builds of the main project. The changes implemented here are quick and dirty - they work for my purposes, but are not held to the same standards of quality or stability as the main project. Use at your own risk! Consider this an unofficial playground for experiments and rapid prototyping rather than a robust or supported software package.

## Get Started

We have tried to simplify the onboarding process as much as possible. It is no longer required to build Willow yourself.
All you have to do is run Willow Application Server and connect to it. From there, you will be guided to the Willow Web Flasher, which will download a Willow release image from Github, inject your Wi-Fi credentials and WAS URL into the NVS partition, and flash it to your device.

### Running WAS

```
docker run --detach --name=willow-application-server --pull=always --network=host --restart=unless-stopped --volume=was-storage:/app/storage ghcr.io/kovrom/willow-application-server:wac
```

### Building WAS
```
git clone https://github.com/kovrom/willow-application-server.git && cd willow-application-server

./utils.sh build

./utils.sh build-web-ui
```

### Start WAS after building it
```./utils.sh run```

## Configure and Upgrade Willow Devices
Visit ```http://my_was_host:8502``` in your browser.   
### Pausing/Ducking volume on willow wake  
This fork of WAS makes a web request PUT on wake and wake end with data payloads  "wake" and "wake_end" with <webhook_id> being your willow box hostname.   
This allows to run automation, for example pause music or lower volume, etc., while willow is listening to your command.  
You can setup where WAS sends PUT request in WAS UI.  Set "Webhook URL" in the format of "http://your_hass_ip:8123/api/webhook/" and enable "Send Webhook command on Wake" and restart WAS.  
Then in your HA you can do the following automation:
```
alias: Pause music webhook
description: ""
trigger:
  - platform: webhook
    allowed_methods:
      - POST
      - PUT
    local_only: true
    webhook_id: willow-xxxxxxxxxx
condition: []
action:
  - if:
      - condition: template
        value_template: "{{ trigger.data['key'] == 'wake' }}"
      - condition: state
        entity_id: media_player.your_player
        state: playing
    then:
      - service: media_player.media_pause
        metadata: {}
        data: {}
        target:
          entity_id: media_player.your_player

    else:      
      - service: media_player.media_play
        metadata: {}
        data: {}
        target:
          entity_id: media_player.your_player      
mode: single
```
### Wilow Auto Correct (WAC)   
To enable WAC go to Configiration -> Advanced, enable Willow Auto Correct (EXPERIMENTAL) and WAS Command Endpoint (EXPERIMENTAL). Restart WAS container.

### Forwarding command when nothing macthed at all 
Some people find it usefull to do something on "Sorry I couldn't understand that" when all else fails. For example you may want to forward not macthed command to your amazon echo dot, chatgpt or want your HA do something else.      
It's also possible to configure which Willow device triggers which specific automation or Amazon Echo Dot, Google speaker, etc.       
For example, you can make it so your "kitchen" Willow only triggers kitchen automations and/or the kitchen Echo Dot, your "office" Willow only triggers office automations and/or the office Echo Dot, etc.     

To do that:
1. In HA create automation that you want to be triggered. Choose a Sentence Trigger, in the format of: "Your_Trigger-Willow_Hostname", where "Willow_Hostname" is the hostname of your willow, you can get it from WAS Clients page.  For example my kitchen willow hostname is "willow-xxxxxxxxxxxx", so:

  Sentence Trigger:
  
  ```
  Ask Echo-willow-xxxxxxxxxxxx {request}
  ```

   Add Actions, for example:

   ```
   service: media_player.play_media
   data:
     media_content_type: custom
     media_content_id: "{{ trigger.slots.request }}"
   target:
      entity_id:
        - media_player.echo_dot_kitchen
   ``` 
2. In your wac `.env` file add:

```
FORWARD_TO_CHAT=True
COMMAND_FINAL_HA_FORWARD="Ask Echo"

```
### To adjust how WAC responds, what commands not to autolearn/skip, etc add and edit following to `.env` file:
```
COMMAND_LEARNED="Learned new command."
COMMAND_CORRECTED="I used command"
COMMANDS_TO_SKIP='["Ask", "Tell Echo"]'
FEEDBACK=True 
```

### Area awareness, kind of...

Not the smartest way to do it, but hey, it works for me for the time being :man_shrugging:

In your wac `.env` file add. Where "willow-xxxxxxxxxxx0" is your willow hostname and "office" is your HA area:

```
AREA_AWARENESS=True
WILLOW_LOCATIONS='{"willow-xxxxxxxxxxx0": "office", "willow-xxxxxxxxxxx1": "kitchen", "willow-xxxxxxxxxxx2": "bedroom"}'

```
By default the following areas are defined: "bedroom", "breakfast room", "dining room", "garage", "living room", "kitchen", "office", "all"     
And two default keywords for "area aware" commands are: "turn", "switch"    
If you would like to override them you can do so in the .env file. Where AREA_AWARE_COMMANDS are keywords for "area aware" commands and HA_AREAS are your HA areas:

```
AREA_AWARE_COMMANDS='["turn","switch","something", "something", "dark side" ]'

HA_AREAS='["bedroom","attic","holodeck"]'

``` 
### Updating/creating .env file   
If you used `docker run` command mentioned in the "Running WAS" section:
1. Create your `.env` file with all the variables, for example:
```
COMMAND_LEARNED="Learned new command."
COMMAND_CORRECTED="I used command"
COMMANDS_TO_SKIP='["Ask","Tell Echo"]'
FORWARD_TO_CHAT=True
COMMAND_FINAL_HA_FORWARD="Ask Echo"
WILLOW_LOCATIONS='{"willow-xxxxxxxxxxx0": "office", "willow-xxxxxxxxxxx1": "kitchen", "willow-xxxxxxxxxxx2": "bedroom"}'
AREA_AWARENESS=True
```
2. Copy it to WAS container:
```
docker cp .env willow-application-server:/app
```
3. restart your WAS container:
```
docker restart willow-application-server
```   
## Upgrading "Over the Air" (OTA)

OTA upgrades allow you to update Willow devices without having to re-connect them to your computer to flash. It's a very safe process with a great deal of verification, automatic rollbacks on upgrade failure, etc.

We list published releases with OTA assets. Select the desired release and click the "Upgrade" button. If the release is not already cached in WAS, WAS will download the binary from Github and cache it, then instruct the target Willow device to start the upgrade from your running WAS instance. Alternatively, you can just upgrade the device from the clients page and WAS will cache it automatically on first request. This makes it possible to run Willow in an isolated VLAN without Internet access.

### Upgrade with your own Willow builds

After building with Willow you can provide your build to WAS to upgrade your local devices using OTA.

Make sure you select the appropriate target hardware from the "Audio HAL" section during build. Then run `./utils.sh build` as you normally would.

To use your custom binary for OTA place `build/willow.bin` from your Willow build directory in the `ota/local` directory of the was-storage volume using the following filenames:

* ESP32-S3-BOX-3.bin
* ESP32-S3-BOX.bin
* ESP32-S3-BOX-LITE.bin

To copy the file to your WAS instance:
```
docker cp build/willow.bin willow-application-server:/app/storage/ota/local/ESP32-S3-BOX-3.bin
```

Your provided build will now be available as the "local" release under the various upgrade options available in the Willow Web UI. You can copy new builds and upgrade however you see fit as you do development and create new Willow builds. If you run into a boot loop, bad flash, etc you can always recover your device from the Willow Web Flasher or Willow build system and try again.
