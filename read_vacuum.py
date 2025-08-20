#!/usr/bin/env python3
import vacuumgaugereadout as vgr
import mattermostpython as mp
import traceback

################################################################################
def main() -> None:
    """
    Try to create the Mattermost interface and send a message if there's an
    exception

    Parameters
    ==========
    interface : mattermostpython.MattermostInterface
        The incoming webhook for posting messages to Mattermost
    """
    # Create the gauges
    gauges, script_id, mattermost_url = vgr.create_gauges_from_command_line_arguments()
    if gauges == None:
        print("Error occurred")
        exit

    # Create the mattermost interface for all messages
    interface = vgr.init_mattermost_interface( mattermost_url )
    
    # Now run the script
    try:
        vgr.start_threads( interface, script_id)
    except Exception as e:
        print(traceback.format_exc())
        if interface != None:
            interface.post_message_from_exception(e)


################################################################################
if __name__ == "__main__":
    main()
