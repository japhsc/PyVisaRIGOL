#!/usr/bin/env python

"""
Inspired by pklaus/rigol-plot.py, forked from shirriff/rigol-plot.py
https://gist.github.com/pklaus/7e4cbac1009b668eafab

Download data from a Rigol DS1052E oscilloscope and graph with matplotlib.
By Ken Shirriff, http://righto.com/rigol

Based on http://www.cibomahto.com/2010/04/controlling-a-rigol-oscilloscope-using-linux-and-python/
by Cibo Mahto.
"""

import numpy
import visa

class ResourceManager(object):
    def __init__(self, **kwargs):
        self.rm = visa.ResourceManager(**kwargs)
        #self.rm = visa.ResourceManager('@py',**kwargs)
        #self.rm = visa.ResourceManager('@ni',**kwargs)

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
    rm = visa.ResourceManager()
    #rm = visa.ResourceManager('@py')
    #rm = visa.ResourceManager('@ni')
    # Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
    instruments = rm.list_resources()
    usb = list(filter(lambda x: 'USB' in x, instruments))
    return usb


def read(adr,channel=1):
    rm = visa.ResourceManager()
    #rm = visa.ResourceManager('@py')
    #rm = visa.ResourceManager('@ni')
    #with Instrument(rm, adr, timeout=2000, chunk_size=1024000) as scope:
    with Instrument(rm, adr) as scope:
        scope.write(':KEY:LOCK')
        scope.write(':RUN')
        scope.write(':ACQuire:MDEPth 600000')
        #scope.write(':ACQuire:MDEPth '+mem_depth+'\n')
        #scope.write(':CHANnel'+str(channel)+':COUPling '+ch_cpl_mode+'\n')
        
        # Record data of a single trigger
        scope.write(':SINGle')
        # Grab the raw data from channel 1
        #scope.write(u':STOP\n')
        
        mem_depth = scope.query(':ACQuire:MDEPth?')[:-1]
        sample_rate = scope.query(':ACQuire:SRATe?')[:-1]

        scope.write(':WAV:SOUR CHAN'+str(channel))

        # Get time scale and offset
        timescale = float(scope.query(':TIM:SCAL?')[:-1])
        timeoffset = float(scope.query(':TIM:OFFS?')[:-1])
        # Get voltage scale and offset
        voltscale = float(scope.query(':CHAN'+str(channel)+':SCAL?')[:-1])
        voltoffset = float(scope.query(':CHAN'+str(channel)+':OFFS?')[:-1])
        
        y_inc = float(scope.query(':WAVeform:YINCrement?')[:-1])
        y_ref = float(scope.query(':WAVeform:YREFerence?')[:-1])
        y_ori = float(scope.query(':WAVeform:YORigin?')[:-1])
        
        x_inc = float(scope.query(':WAVeform:XINCrement?')[:-1])
        x_ref = float(scope.query(':WAVeform:XREFerence?')[:-1])
        x_ori = float(scope.query(':WAVeform:XORigin?')[:-1])
        
        print(scope.query(':WAVeform:PREamble?'))
        scope.write(':WAVeform:FORMat BYTE')
        
        #scope.write(':WAVeform:MODE RAW')
        scope.write(':WAVeform:MODE NORMAL')
        #rawdata = scope.query(':WAV:DATA? CHAN'+str(channel)+'\n').encode('ascii')[10:-1]
        scope.write(':WAV:DATA? CHAN'+str(channel)) #Request the data
        rawdata = scope.read_raw() #Read the block of data
        head = rawdata[:11]
        rawdata = rawdata[11:-1] #Drop the heading
        #print(rawdata[:20])
        print(head)

        data_size = len(rawdata)

        scope.write(':RUN')
        scope.write(':KEY:FORCE')
        scope.close()
        
        print('Data size:', data_size, "Sample rate:", sample_rate, "Mem. depth", mem_depth)

        

    data = numpy.frombuffer(rawdata, 'B').astype(float)
    #print(data[0:20])
    #print(data.dtype)
    #print(y_ori,y_ref,y_inc)
    data = (data - y_ori - y_ref) * y_inc
    
    # dt = :TIM:SCAL?/50
    # y_offs = :OFFS?
    # y_inc = :TIM:SCALE?/25
    # y_ref = 125
    # y_hex = data
    #data = (y_ref - y_hex)*y_inc - y_offs
    print(data[0:20])
    print(((data[0:20]*-1 + 255) - 130.0 - voltoffset/voltscale*25) / 25 * voltscale)

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


