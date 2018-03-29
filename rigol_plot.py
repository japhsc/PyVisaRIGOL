#!/usr/bin/env python

"""
Download data from a Rigol DS1052E oscilloscope and graph with matplotlib.
By Ken Shirriff, http://righto.com/rigol

Based on http://www.cibomahto.com/2010/04/controlling-a-rigol-oscilloscope-using-linux-and-python/
by Cibo Mahto.
"""

import numpy
import visa

class ResourceManager(object):
    def __init__(self, **kwargs):
        #self.rm = visa.ResourceManager(**kwargs)
        self.rm = visa.ResourceManager('@py',**kwargs)

    def __enter__(self):
        return(self.rm)

    def __exit__(self, exc_type, exc, exc_tb):
        del(self.rm)

class Instrument(object):
    def __init__(self, rm, resource_name, **kwargs):
        self.inst = rm.open_resource(resource_name, **kwargs)

    def __enter__(self):
        return(self.inst)

    def __exit__(self, exc_type, exc, exc_tb):
        self.inst.close()
        

def list_device():
    #rm = visa.ResourceManager()
    rm = visa.ResourceManager('@py')
    # Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
    instruments = rm.list_resources()
    usb = list(filter(lambda x: 'USB' in x, instruments))
    return usb


def read(adr,channel=1):
    #rm = visa.ResourceManager()
    rm = visa.ResourceManager('@py')
    with Instrument(rm,adr) as scope:
        scope.write(":KEY:LOCK")

        # Grab the raw data from channel 1
        scope.write(u':STOP\n')

        scope.write(':WAV:SOUR CHAN'+str(channel)+'\n')
        
        # Get time scale and offset
        timescale = float(scope.query(u':TIM:SCAL?\n'))
        timeoffset = float(scope.query(u':TIM:OFFS?\n'))
        # Get voltage scale and offset
        voltscale = float(scope.query(u':CHAN'+str(channel)+':SCAL?\n'))
        voltoffset = float(scope.query(u':CHAN'+str(channel)+':OFFS?\n'))
        
        y_inc = float(scope.query(u':WAVeform:YINCrement?\n'))
        y_ref = float(scope.query(u':WAVeform:YREFerence?\n'))
        y_ori = float(scope.query(u':WAVeform:YORigin?\n'))
        
        x_inc = float(scope.query(u':WAVeform:XINCrement?\n'))
        x_ref = float(scope.query(u':WAVeform:XREFerence?\n'))
        x_ori = float(scope.query(u':WAVeform:XORigin?\n'))

        scope.write(":WAV:POIN:MODE RAW")
        rawdata = scope.query(':WAV:DATA? CHAN'+str(channel)+'\n').encode('ascii')[10:-1]
        #print(rawdata)
        data_size = len(rawdata)

        sample_rate = scope.query(':ACQuire:SRATe?')
        print('Data size:', data_size, "Sample rate:", sample_rate)

        scope.write(":RUN")
        scope.write(":KEY:FORCE")
        #scope.close()

    data = numpy.frombuffer(rawdata, 'B')
    data = (data - y_ori - y_ref) * y_inc

    # Walk through the data, and map it to actual voltages
    # This mapping is from Cibo Mahto
    # First invert the data
    #data = data * -1 + 255

    # Now, we know from experimentation that the scope display range is actually
    # 30-229.  So shift by 130 - the voltage offset in counts, then scale to
    # get the actual voltage.
    #data = (data - 130.0 - voltoffset/voltscale*25) / 25 * voltscale

    # Now, generate a time axis.
    time = numpy.linspace(timeoffset - 6 * timescale, 
                          timeoffset + 6 * timescale, 
                          num=len(data))
    return time, data


