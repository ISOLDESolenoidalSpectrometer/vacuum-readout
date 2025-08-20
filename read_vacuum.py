#!/usr/bin/env python3
import vacuumgaugereadout as vgr
import mattermostpython as mp
import traceback
from typing import List

################################################################################
def main( interface : mp.MattermostInterface ) -> None:
    """
    The main body used to set up the threads used to sample the vacuum gauges

    Parameters
    ==========
    interface : mattermostpython.MattermostInterface
        The incoming webhook for posting messages to Mattermost
    """
    # Create the gauges
    gauges, script_id = vgr.create_gauges_from_command_line_arguments()
    if gauges == None:
        print("Error occurred")
        return
    
    # Start the readout
    threads : List[vgr.VacuumGaugeReadoutThread]= []
    for gauge in gauges:
        readout = vgr.VacuumGaugeReadoutThread( gauge, interface )
        threads.append(readout)
        readout.start()

    # Wait for all the threads to rejoin
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        for thread in threads:
            thread.kill_thread()

    # Post message to mattermost to indicate completion of script
    if interface != None:
        interface.post(
            mp.MattermostMessage(
                colour='#FF0000',
                title='Vacuum readout script terminated?',
                text=f'A vacuum script terminated with id {script_id}. If this wasn\'t planned, please restart it'
            )
        )

    return


################################################################################
if __name__ == "__main__":
    """
    Try to create the Mattermost interface and send a message if there's an
    exception
    """
    # Create the mattermost interface for all messages
    interface = vgr.init_mattermost_interface( '.mattermost_url.txt' )
    
    # Now run the script
    try:
        main(interface)
    except Exception as e:
        print(traceback.format_exc())
        if interface != None:
            interface.post_message_from_exception(e)
