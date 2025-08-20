import datetime as dt
import enum
import serial
import requests
from typing import Type, TypeVar
import re

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
        Initiialise all the details TODO
        """ 
        # Store constants
        self.serial_number = serial_number
        self.channels = channels
        self.gauge_names = gauge_names
        self.falling_pressure_thresholds = falling_pressure_thresholds
        self.rising_pressure_thresholds = rising_pressure_thresholds
        self.port = None
        self.speed=9600

        self.prev_status   = [None] * len(self.channels)
        self.prev_pressure = [None] * len(self.channels)
        self.cur_status = [None] * len(self.channels)
        self.cur_pressure = [None] * len(self.channels)

        self.alert_pressure_falling = [False] * len(self.channels)
        self.alert_pressure_rising = [False] * len(self.channels)
        
        return

    ################################################################################
    def open_serial_port(self) -> bool:
        """
        TODO
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
        TODO
        """
        update_values = False
        for i in range(len(self.channels)):
            # check if there is a significant change
            if self.prev_pressure[i] is not None and self.prev_pressure[i] > 1e-12:
                if self.cur_pressure[i] / self.prev_pressure[i] > VacuumGauge.UPPER_PRESSURE_LIMIT:
                    update_values = True
                elif self.cur_pressure[i] / self.prev_pressure[i] < VacuumGauge.LOWER_PRESSURE_LIMIT:
                    update_values = True
            
            if self.prev_status[i] is not None and int(self.cur_status[i]) is not int(self.prev_status[i]):
                update_values = True

            #print(i, ": update_ctr = ", update_ctr, ", pressure = ", pressure, ", status", status)

            # update values
            self.prev_pressure[i] = self.cur_pressure[i]
            self.prev_status[i] = self.cur_status[i]
        
        return update_values
    
    ################################################################################
    def get_pressures(self) -> None:
        """
        TODO
        """
        # YOU NEED TO OVERRIDE THIS!
        return
    
    ################################################################################
    def update_alerting_status(self) -> None:
        """
        TODO
        """
        for i in range(0,len(self.channels)):
            if self.cur_pressure[i] < self.falling_pressure_thresholds[i]:
                self.alert_pressure_falling[i] = True
            else:
                self.alert_pressure_falling[i] = False
            
            if self.cur_pressure[i] > self.rising_pressure_thresholds[i]:
                self.alert_pressure_rising[i] = True
            else:
                self.alert_pressure_rising[i] = False
        
        return

    ################################################################################
    def push_to_grafana(self) -> None:
        """
        TODO
        """
        payload = ''
        for i in range(len(self.channels)):
            payload_p = 'pressure,gauge=' + self.gauge_names[i] + ' value=' + ('%.9f' % self.cur_pressure[i])
            payload_s = ',status=' + str(self.cur_status[i]) + '\n'
            payload += payload_p + payload_s

        try:
            r = requests.post('https://dbod-iss.cern.ch:8080/write?db=vacuum', auth = ('admin', 'issmonitor'), data=payload, verify=False, timeout=VacuumGauge.HTTP_TIMEOUT)
            print(f"{dt.datetime.now().strftime( '%Y.%m.%d %H:%M:%S' )} pushed values to Grafana")
        except Exception:
            pass

        return

################################################################################
class MKSGauge(VacuumGaugeBase):
    """
    TODO
    """
    BRAND = 'MKS'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        """
        TODO
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
        TODO
        """
        self.serial.write((cmd + self.LINETERM).encode('ascii') )
        ack = self.serial.readline().decode('ascii')
        return ack

    ################################################################################
    def get_pressures(self) -> None:
        """
        TODO
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
    TODO
    """
    BRAND = 'Pfeiffer'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        """
        TODO
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
        TODO
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
    TODO
    """
    BRAND = 'Edwards'
    ################################################################################
    def __init__(self, serial_number : str, channels : list, gauge_names : list, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None):
        # Edwards-specific code here
        self.LINETERM = '\r'
        self.ENQ = '?'

        # Use parent constructor
        super().__init__(serial_number, channels, gauge_names)
        return

    ################################################################################
    def get_pressures(self) -> None:
        """
        TODO
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
    TODO
    """
    PFEIFFER = 'pfeiffer'
    MKS = 'mks'
    EDWARDS = 'edwards'

    ################################################################################
    @classmethod
    def get_brand_from_str( cls : Type[T], brand : str ) -> T:
        """
        TODO
        """
        for member in GaugeBrand:
            if member.value == brand:
                return member
        
        raise ValueError(f'{brand} is not a valid gauge brand!')
        

################################################################################
def VacuumGauge( brand : GaugeBrand, serial_number : str, channels : list, gauge_names, falling_pressure_thresholds : list = None, rising_pressure_thresholds : list = None ) -> VacuumGaugeBase:
    if brand == GaugeBrand.PFEIFFER:
        return PfeifferGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    if brand == GaugeBrand.MKS:
        return MKSGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    if brand == GaugeBrand.EDWARDS:
        return EdwardsGauge( serial_number, channels, gauge_names, falling_pressure_thresholds, rising_pressure_thresholds )
    raise ValueError("Did not recognise gauge brand {brand}. Cannot create new gauge object.")