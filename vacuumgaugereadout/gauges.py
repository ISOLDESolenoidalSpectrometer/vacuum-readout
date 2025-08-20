import argparse as ap
import datetime as dt
import enum
import serial
import requests
import traceback
from typing import List, Type, TypeVar
import re

from . import grafanaauthentication as ga
from . import utils

################################################################################
class VacuumGaugeBase:
    """
    Base class used for reading out a vacuum gauge. Through the power of
    polymorphism, its methods can then be redefined and called for many different
    kinds of gauges
    """
    HTTP_TIMEOUT = 10
    PRESSURE_CHANGE_THRESHOLD = 0.005 # change of 0.05% enough to trigger an update
    UPPER_PRESSURE_LIMIT = 1.0 + PRESSURE_CHANGE_THRESHOLD
    LOWER_PRESSURE_LIMIT = 1.0 - PRESSURE_CHANGE_THRESHOLD
    BRAND = 'BASE CLASS GAUGE'

    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None ):
        """
        Initiialise all the details

        Parameters
        ==========
        serial_number : str
            The serial number of the gauge with which we wish to communicate
        channels : list
            The list of channels we need to communicate with on the gauge
        gauge_names : list
            The list of names we wish to use when pushing to Grafana
        falling_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure falls below a certain value.
        rising_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure rises above a certain value.
        
        """ 
        # Store constants
        self.serial_number = serial_number
        self.channels = channels
        self.gauge_names = gauge_names
        self.falling_pressure_thresholds = falling_pressure_thresholds
        self.rising_pressure_thresholds = rising_pressure_thresholds

        # Check whether we should send alerts
        self.enable_falling_pressure_alerts = bool(utils.count_numbers_in_list(falling_pressure_thresholds))
        self.enable_risiing_pressure_alerts = bool(utils.count_numbers_in_list(rising_pressure_thresholds))

        self.port = None
        self.speed=9600

        self.prev_status   = [None] * len(self.channels)
        self.prev_pressure = [None] * len(self.channels)
        self.cur_status = [None] * len(self.channels)
        self.cur_pressure = [None] * len(self.channels)

        self.alert_pressure_falling = [False] * len(self.channels)
        self.alert_pressure_rising = [False] * len(self.channels)
        self.grafana_username, self.grafana_password, self.grafana_url = None, None, None    
        return

    ################################################################################
    def set_grafana_authentication(self, auth : tuple) -> None:
        """
        Stores the username, password, and URL for Grafana
        """
        self.grafana_username, self.grafana_password, self.grafana_url = auth
        return

    ################################################################################
    def open_serial_port(self) -> bool:
        """
        Opens the serial port

        Returns
        =======
        status : bool
            True if it worked, False if it didn't
        """
        if self.port == None:
            return False
        
        self.serial = serial.Serial(port=self.port, baudrate=self.speed, timeout=1)
        self.serial.flushInput()
        self.serial.flushOutput()
        return True
    
    ################################################################################
    def check_if_update_needed(self) -> bool:
        """
        Checks if the values of the pressure should be updated, based on whether they have changed enough
        
        Returns
        =======
        status : bool
            True if it needs to update, False otherwise
        """
        update_values = False
        for i in range(len(self.channels)):
            # check if there is a significant change
            if self.prev_pressure[i] is not None and self.prev_pressure[i] > 1e-12:
                if self.cur_pressure[i] / self.prev_pressure[i] > VacuumGaugeBase.UPPER_PRESSURE_LIMIT:
                    update_values = True
                elif self.cur_pressure[i] / self.prev_pressure[i] < VacuumGaugeBase.LOWER_PRESSURE_LIMIT:
                    update_values = True
            
            if self.prev_status[i] is not None and int(self.cur_status[i]) is not int(self.prev_status[i]):
                update_values = True

            # update values
            self.prev_pressure[i] = self.cur_pressure[i]
            self.prev_status[i] = self.cur_status[i]
        
        return update_values
    
    ################################################################################
    def get_pressures(self) -> None:
        """
        Abstract method that needs to be overwritten for each child class to get the
        pressures from their gauges
        """
        # YOU NEED TO OVERRIDE THIS!
        return
    
    ################################################################################
    def update_alerting_status(self) -> None:
        """
        Checks if pressure is rising or falling and sets some internal flags if
        someone needs to be alerted
        """
        for i in range(0,len(self.channels)):
            if self.enable_falling_pressure_alerts:
                if self.cur_pressure[i] < self.falling_pressure_thresholds[i]:
                    self.alert_pressure_falling[i] = True
                else:
                    self.alert_pressure_falling[i] = False
            
            if self.enable_risiing_pressure_alerts:
                if self.cur_pressure[i] > self.rising_pressure_thresholds[i]:
                    self.alert_pressure_rising[i] = True
                else:
                    self.alert_pressure_rising[i] = False
        
        return

    ################################################################################
    def push_to_grafana(self) -> None:
        """
        Pushes a payload to Grafana
        """
        payload = ''
        for i in range(len(self.channels)):
            payload_p = 'pressure,gauge=' + self.gauge_names[i] + ' value=' + ('%.9f' % self.cur_pressure[i])
            payload_s = ',status=' + str(self.cur_status[i]) + '\n'
            payload += payload_p + payload_s

        try:
            r = requests.post(self.grafana_url, auth = (self.grafana_username, self.grafana_password), data=payload, verify=False, timeout=VacuumGaugeBase.HTTP_TIMEOUT)
            print(f"{dt.datetime.now().strftime( '%Y.%m.%d %H:%M:%S' )} pushed values to Grafana")
        except Exception as e:
            print(e)
            traceback.print_exc()

        return

################################################################################
class MKSGauge(VacuumGaugeBase):
    """
    MKS gauge - used for ISS backing pressure
    """
    BRAND = 'MKS'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        """
        Specific initialisation for MKS gauge

        Parameters
        ==========
        serial_number : str
            The serial number of the gauge with which we wish to communicate
        channels : list
            The list of channels we need to communicate with on the gauge
        gauge_names : list
            The list of names we wish to use when pushing to Grafana
        falling_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure falls below a certain value.
        rising_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure rises above a certain value.
        """
        # MKS-specific code here
        self.LINETERM = '\x0D'+'\x0A'
        self.ENQ = '\x05'

        # Use parent constructor
        super().__init__(serial_number, channels, gauge_names)

        return
    
    ################################################################################
    def send_command(self, cmd : str) -> str:
        """
        Helpful command for sending messages to the MKS gauge
        """
        self.serial.write((cmd + self.LINETERM).encode('ascii') )
        ack = self.serial.readline().decode('ascii')
        return ack

    ################################################################################
    def get_pressures(self) -> None:
        """
        Overwritten method to get pressures on the MKS gauge
        """
        if self.open_serial_port():
            # Log every second
            self.send_command('@253DLT!00:00:01;FF')

            # Start logging
            self.send_command('@253DLC!START;FF')

        for i in range(len(self.channels)):
            # Read data logging
            line = self.send_command('@253DL?;FF')

            # Extract the pressure from a string like
                        # '@253ACK@253ACKTime;MP: mbar\r00:00:00;2.00e-02\r00:00:01;2.00e-02\r\x03;FF'"
            try:
                line = line.split('\r') # split by \r
                line = line[len(line)-2] # the penultimate one has a timestamp;pressure
                line = line.split(';')[1] # get the pressure
                self.cur_pressure[i] = float(line)
                self.cur_status[i] = 0
            except:
                pass
            
            # Start a fresh data logging
            self.send_command('@253DLC!START;FF')
        return

################################################################################
class PfeifferGauge(VacuumGaugeBase):
    """
    Pfeiffer gauge - used for the upstream pressure
    """
    BRAND = 'Pfeiffer'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        """
        Pfeiffer initialisation

        Parameters
        ==========
        serial_number : str
            The serial number of the gauge with which we wish to communicate
        channels : list
            The list of channels we need to communicate with on the gauge
        gauge_names : list
            The list of names we wish to use when pushing to Grafana
        falling_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure falls below a certain value.
        rising_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure rises above a certain value.
        """
        # Pfeiffer-specific code here
        self.LINETERM = '\x0D'+'\x0A'
        self.ENQ = '\x05'

        # Use parent constructor
        super().__init__(serial_number, channels, gauge_names)
        return
    
    ################################################################################
    def get_pressures(self) -> None:
        """
        Overwritten method to get pressures on the Pfeiffer gauge
        """
        for i in range(len(self.channels)):
            self.serial.write(('PR' + str(self.channels[i]) + self.LINETERM).encode('ascii') )
            ack = self.serial.readline()
            self.serial.write((self.ENQ).encode('ascii'))
            res = self.serial.readline().decode('ascii')
            t = res.split(',')
            res = t[1]
            self.cur_status[i] = t[0]
            self.cur_pressure[i] = float(res[1:])
        
        return

################################################################################
class EdwardsGauge(VacuumGaugeBase):
    """
    Edwards gauge - used for ISS ionisation chamber
    """
    BRAND = 'Edwards'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        """
        Edwards initialisation

        Parameters
        ==========
        serial_number : str
            The serial number of the gauge with which we wish to communicate
        channels : list
            The list of channels we need to communicate with on the gauge
        gauge_names : list
            The list of names we wish to use when pushing to Grafana
        falling_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure falls below a certain value.
        rising_pressure_thresholds : list
            The list of pressure thresholds on a channel-by-channel basis. Default is None.
            This is triggered when the pressure rises above a certain value.
        """
        # Edwards-specific code here
        self.LINETERM = '\r'
        self.ENQ = '?'

        # Use parent constructor
        super().__init__(serial_number, channels, gauge_names)
        return

    ################################################################################
    def get_pressures(self) -> None:
        """
        Overwritten method to get pressures on Edwards gauge
        """
        for i in range(len(self.channels)):
            self.serial.write(('?GA' + str(self.channels[i]) + self.LINETERM).encode('ascii') )
            res = self.serial.readline().decode('ascii')
            print(repr(res))
            pattern = re.match(r'(Err)(\d*)', res, re.IGNORECASE)
            if pattern is not None:
                self.cur_pressure[i] = 1010
                self.cur_status[i] = int(pattern.group(2))
            else:
                self.cur_pressure[i] = float(res.strip('\r'))
                self.cur_status[i] = 0
        return

################################################################################
T = TypeVar("T", bound="GaugeBrand")

class GaugeBrand(enum.Enum):
    """
    Simple ENUM class to determine gauge type
    """
    PFEIFFER = 'pfeiffer'
    MKS = 'mks'
    EDWARDS = 'edwards'

    ################################################################################
    @classmethod
    def get_brand_from_str( cls : Type[T], brand : str ) -> T:
        """
        Method to convert string to enum
        """
        for member in GaugeBrand:
            if member.value == brand:
                return member
        
        raise ValueError(f'{brand} is not a valid gauge brand!')
        

################################################################################
def VacuumGauge( brand : GaugeBrand, serial_number : str, channels : list, gauge_names, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None ) -> VacuumGaugeBase:
    """
    Custom constructor function for each gauge type.

    Parameters
    ==========
    brand : GaugeBrand(enum)
        enum stating which brand the gauge belongs to - this is used to call the right constructor
    serial_number : str
        The serial number of the gauge with which we wish to communicate
    channels : list
        The list of channels we need to communicate with on the gauge
    gauge_names : list
        The list of names we wish to use when pushing to Grafana
    falling_pressure_thresholds : list
        The list of pressure thresholds on a channel-by-channel basis. Default is None.
        This is triggered when the pressure falls below a certain value.
    rising_pressure_thresholds : list
        The list of pressure thresholds on a channel-by-channel basis. Default is None.
        This is triggered when the pressure rises above a certain value.
    """
    if brand == GaugeBrand.PFEIFFER:
        return PfeifferGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    if brand == GaugeBrand.MKS:
        return MKSGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    if brand == GaugeBrand.EDWARDS:
        return EdwardsGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    raise ValueError("Did not recognise gauge brand {brand}. Cannot create new gauge object.")


################################################################################
def create_gauges_from_command_line_arguments() -> list:
    """
    A function that converts command-line arguments into a list of VacuumGaugeBase objects

    Returns
    =======
    list_of_gauges : list[VacuumGaugeBase]
        A list of VacuumGaugeBase objects
    """
    parser = ap.ArgumentParser(prog='', description='', epilog='')
    parser.add_argument('-b', '--brand',                       help='brand of the vacuum gauge (\'pfeiffer\', \'edwards\', or \'mks\')',         metavar='BRAND',    default=None, dest='brand',         action='append' )
    parser.add_argument('-s', '--serial-number',               help='serial number of the vacuum gauge',                                         metavar='SN',       default=None, dest='serialnumber',  action='append' )
    parser.add_argument('-c', '--channels',                    help='list of channels to sample on the gauge',                                   metavar='CHAN',     default=None, dest='channel',       action='append' )
    parser.add_argument('-g', '--grafana-label',               help='name of the gauge in Grafana',                                              metavar='GRAFNAME', default=None, dest='grafana',       action='append' )
    parser.add_argument('-R', '--rising-pressure-threshold',   help='pressure (in mbar) above which to send an alert saying something is wrong', metavar='RP',       default=None, dest='rpthresh',      action='append' )
    parser.add_argument('-F', '--falling-pressure-threshold',  help='pressure (in mbar) below which to send an alert saying everything is OK',   metavar='FP',       default=None, dest='fpthresh',      action='append' )
    parser.add_argument('-i', '--id',                          help='identifier for which instance of the script, in case something goes wrong', metavar='ID',       default=None, dest='id',            action='store' )
    parser.add_argument('-G', '--grafana-authentication',      help='grafana authentication file path',                                          metavar='GrafAuth', default=None, dest='grafauth',      action='store' )
    args = parser.parse_args()

    # Store arguments here
    serial_numbers = args.serialnumber
    brands = args.brand
    channels = args.channel
    grafana = args.grafana
    rising_pressure_thresholds = args.rpthresh
    falling_pressure_thresholds = args.fpthresh
    id = args.id
    grafana_file_path = args.grafauth


    # Check if nothing provided for thresholds and convert to list
    if falling_pressure_thresholds == None:
        falling_pressure_thresholds = [None]*len(channels)
    if rising_pressure_thresholds == None:
        rising_pressure_thresholds = [None]*len(channels)

    # Convert grafana names, channel names, and thresholds
    for i in range(len(channels)):
        channels[i] = utils.csv_str_to_list( channels[i], int )
        grafana[i] = utils.csv_str_to_list( grafana[i], str )
        falling_pressure_thresholds[i] = utils.csv_str_to_list( falling_pressure_thresholds[i], float )
        rising_pressure_thresholds[i] = utils.csv_str_to_list( rising_pressure_thresholds[i], float )

    # Possibility that no pressure thresholds specified. Ensure they are the same length with "None"
    falling_pressure_thresholds = utils.create_optimal_thresholds_from_channels( channels, falling_pressure_thresholds )
    rising_pressure_thresholds = utils.create_optimal_thresholds_from_channels( channels, rising_pressure_thresholds )

    # Check same number for each item
    if len(serial_numbers) != len(brands) or \
       len(serial_numbers) != len(brands) or \
       len(serial_numbers) != len(channels) or \
       len(serial_numbers) != len(grafana) or \
       len(serial_numbers) != len(falling_pressure_thresholds) or \
       len(serial_numbers) != len(rising_pressure_thresholds):
        print(f"Serial numbers:           {len(serial_numbers)}")
        print(f"Brands:                   {len(brands)}")
        print(f"Channels:                 {len(channels)}")
        print(f"Grafana name:             {len(grafana)}")
        print(f"High-pressure thresholds: {len(rising_pressure_thresholds)}")
        print(f"Low-pressure thresholds:  {len(falling_pressure_thresholds)}")
        print("Must be same number of every item to initialise gauges correctly. ERROR!")
        return None
    
    # Check same length for channels, grafana names - pressure thresholds already checked!
    for i in range(0,len(channels)):
        if len(channels[i]) != len(grafana[i]):
            raise IndexError(f"Mismatch between number of channels = {channels[i]} and list of grafana names = {grafana[i]}")
        
    # Check brand names
    for i in range(0,len(brands)):
        while type( brands[i] ) == list:
            if len(brands[i]) > 1:
                raise IndexError(f"Cannot parse object with length > 1: {brands}")
            brands[i] = brands[i][0]
        
        brands[i] = GaugeBrand.get_brand_from_str( brands[i] )

    # Turn gauge numbers into a list of numbers
    list_of_gauges : List[VacuumGaugeBase] = []
    for i in range(0,len(serial_numbers)):
        list_of_gauges.append( VacuumGauge( brands[i], serial_numbers[i], channels[i], grafana[i], falling_pressure_thresholds, rising_pressure_thresholds ) )

    # Set Grafana authentication
    auth = ga.get_grafana_authentication( grafana_file_path )

    for gauge in list_of_gauges:
        gauge.set_grafana_authentication( auth )

    # Sanitise ID input
    if id == None:
        id = '[someone forgot to identify the script - more work for you!]'

    return list_of_gauges, id