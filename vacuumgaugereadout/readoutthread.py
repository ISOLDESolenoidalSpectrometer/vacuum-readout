"""
Vacuum readout thread
=====================

Defines the VacuumGaugeReadoutThread object, which is used to sample the pressure
from the gauge according to UPDATE_TIME
"""
################################################################################

from serial.tools import list_ports
import threading
import time
import traceback

from . import gauges
from . import grafanaauthentication as ga
import mattermostpython as mp

class VacuumGaugeReadoutThread( threading.Thread ):
    """
    Samples the gauge according to UPDATE_TIME and pushes the data to Grafana. Also
    sends alerts to Mattermost.
    """
    UPDATE_TIME = 0.5 #seconds

    ################################################################################
    def __init__(self, gauge : gauges.VacuumGaugeBase, mattermost_interface : mp.MattermostInterface = None ):
        """
        Initialise the thread

        Parameters
        ==========
        gauge : VacuumGaugeBase
            The gauge object which will be sampled
        grafana_file : str
            The file path to the Grafana authentication details
        mattermost_interface : mattermostpython.MattermostInterface
            The interface for posting messages to Mattermost
        """
        # Find out the serial ports for each gauge
        ports = list_ports.comports()

        for port in ports:
            if port.serial_number == gauge.serial_number:
                gauge.port = port.device
                break

        # Store gauge
        self.gauge = gauge if gauge.port != None else None

        if self.gauge == None:
            raise ValueError(f"ValueError: Could not find gauge of the given serial number {gauge.serial_number}")

        # Store mattermost interface
        self.mattermost = mattermost_interface

        # Store alert pressure items
        self.alert_pressure_falling = [False]*len(self.gauge.channels)
        self.alert_pressure_rising = [False]*len(self.gauge.channels)

        # Call parent threading constructor
        super().__init__()

    ################################################################################
    def send_mattermost_message( self, message : mp.MattermostMessage ) -> None:
        """
        Handy method to send messages to Mattermost

        Parameters
        ==========
        message : mattermostpython.MattermostMessage
            MattermostMessage object to send to Mattermost
        """
        if message == None:
            return

        if self.mattermost != None:
            self.mattermost.post( message )

        return

    ################################################################################
    def construct_mattermost_message(self, channel_index : int, pressure_is_falling : bool ) -> mp.MattermostMessage:
        """
        Constructs a mattermost message based on the channel index and whether the pressure is falling or rising

        Parameters
        ==========
        channel_index : int
            The index of the channel in the list of channels as part of the gauge object
        pressure_is_falling : bool
            Indicator of whether pressure is rising or pressure is falling

        Returns
        =======
        message : mattermostpython.MattermostMessage
            Message to send to Mattermost
        """
        message = mp.MattermostMessage()
        message.set_colour( '#FF0000' if pressure_is_falling else '#00FF00')
        message.set_author_name( f"{self.gauge.BRAND} gauge: {self.gauge.serial_number}, channel {self.gauge.channels[channel_index]} ({self.gauge.gauge_names[channel_index]})" )
        message.add_field( mp.MattermostField( True, 'Current pressure (mbar)', str(self.gauge.cur_pressure[channel_index])) )

        if pressure_is_falling:
            message.set_title( f'Pressure is good ({self.gauge.gauge_names[channel_index]})')
            message.set_text(
                f'The pressure on the {self.gauge.BRAND} gauge ({self.gauge.gauge_names[channel_index]}) has fallen below the alert point. Good news!'
            )
            message.set_priority( mp.MattermostMessagePriority.STANDARD )
            message.add_field( mp.MattermostField( True, 'Threshold pressure (mbar)', str(self.gauge.falling_pressure_thresholds[channel_index])) )
        else:
            message.set_title( f'Pressure is bad ({self.gauge.gauge_names[channel_index]})')
            message.set_priority( mp.MattermostMessagePriority.URGENT )
            message.set_text(
                f'The pressure on the {self.gauge.BRAND} gauge ({self.gauge.gauge_names[channel_index]}) has risen above the alert point. If this is unexpected, please take action and deal with it!'
            )
            message.add_field( mp.MattermostField( True, 'Threshold pressure (mbar)', str(self.gauge.rising_pressure_thresholds[channel_index])) )

        return message


    ################################################################################
    def update_alerting_status(self) -> None:
        """
        Works out whether to send a message or not based on the changes in pressure
        """
        # Update alerting status
        self.gauge.update_alerting_status()

        # Fallen below low pressure limit - this is good!
        for i in range(0,len(self.gauge.channels)):
            if self.alert_pressure_falling[i] == False and self.gauge.alert_pressure_falling[i] == True:
                self.alert_pressure_falling[i] = True
                self.send_mattermost_message( self.construct_mattermost_message( i, True ) )

            # Risen above falling pressure limit - don't post anything...
            elif self.alert_pressure_falling == True and self.gauge.alert_pressure_falling == False:
                self.alert_pressure_falling = False

            # Risen above high pressure limit - this is bad!
            if self.alert_pressure_rising == False and self.gauge.alert_pressure_rising == True:
                self.alert_pressure_rising = True
                self.send_mattermost_message( self.construct_mattermost_message( i, False ) )

            # Fallen below rising pressure limit - don't post anything...
            elif self.alert_pressure_rising == True and self.gauge.alert_pressure_falling == False:
                self.alert_pressure_rising = False
        
        return


    ################################################################################
    def run(self) -> None:
        """
        The main body of the thread loop
        """
        if self.gauge == None:
            return

        # Initialise pressures and status
        update_ctr = 0

        # Open serial port
        if not self.gauge.open_serial_port():
            print(f"Could not open serial port {self.gauge.port}")
            return

        # Loop for infinity
        try:
            while True:
                # worth sending to influx?
                update_values = False

                # Counter to update at least once per minute
                update_ctr = update_ctr + 1
                if update_ctr > 60:
                    update_values = True

                # Get pressures
                self.gauge.get_pressures()

                # Check if update needed
                update_values += self.gauge.check_if_update_needed()

                # Update alerting status
                self.update_alerting_status()

                # Send to influx if needed for both gauges together
                if update_values:
                    self.gauge.push_to_grafana()
                    update_ctr = 0

                # wait for next loop
                time.sleep(VacuumGaugeReadoutThread.UPDATE_TIME)

        except Exception as e:
            # Send message to Mattermost
            self.send_mattermost_message( mp.MattermostMessage.create_message_from_exception(e) )

            # Print errors to console
            print(e)
            traceback.print_exc()

            # Close connection to gauge
            self.gauge.serial.close()
