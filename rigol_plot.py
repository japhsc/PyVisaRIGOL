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
import os

class ResourceManager(object):
    def __init__(self, **kwargs):
        if os.name == 'posix':
            self.rm = visa.ResourceManager('@py',**kwargs)
        elif os.name == 'nt':
            self.rm = visa.ResourceManager('@ni',**kwargs)
        else:
            self.rm = visa.ResourceManager(**kwargs)
    def __enter__(self):
        return(self.rm)

    def __exit__(self, exc_type, exc, exc_tb):
        del(self.rm)

class Instrument(object):
    def __init__(self, rm, resource_name, **kwargs):
        self.inst = rm.open_resource(resource_name, **kwargs)
        #self.inst.encoding =  "latin-1"
    def __enter__(self):
        #return(self.inst)
        return(self)
    def __exit__(self, exc_type, exc, exc_tb):
        self.inst.close()
    
    def query(self,command):
        #return(self.inst.query(command))
        #return(self.inst.query_binary_values(command, datatype='b', is_big_endian=True))
        self.write(command) #Request the data
        rawdata = self.read_raw()
        data = rawdata
        while (data[-1] is not 10):
            data =  data[:-1]
        while (data[-1] is 10):
            data =  data[:-1]
        #print(data)
        return(data.decode("utf-8"))
        
    def read_raw(self):
        return(self.inst.read_raw()) #Read the block of data
    
    def write(self,command):
        return(self.inst.write(command))


def list_device():
    if os.name == 'posix':
        rm = visa.ResourceManager('@py')
    elif os.name == 'nt':
        rm = visa.ResourceManager('@ni')
    else:
        rm = visa.ResourceManager()

    # Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
    instruments = rm.list_resources()
    usb = list(filter(lambda x: 'USB' in x, instruments))
    return usb


def read(adr,channel=1):
    if os.name == 'posix':
        rm = visa.ResourceManager('@py')
    elif os.name == 'nt':
        rm = visa.ResourceManager('@ni')
    else:
        rm = visa.ResourceManager()
        
    with Instrument(rm, adr, timeout=2000, chunk_size=1024000) as scope:
    #with Instrument(rm, adr) as scope:
        #print(scope.query("*IDN?"))
        
        scope.write(':KEY:LOCK')
        scope.write(':RUN')
        scope.write(':ACQuire:MDEPth 600000')
        #scope.write(':ACQuire:MDEPth '+mem_depth+'\n')
        #scope.write(':CHANnel'+str(channel)+':COUPling '+ch_cpl_mode+'\n')
        
        # Record data of a single trigger
        scope.write(':SINGle')
        # Grab the raw data from channel 1
        #scope.write(u':STOP\n')
        
        mem_depth = scope.query(':ACQuire:MDEPth?')
        sample_rate = scope.query(':ACQuire:SRATe?')

        scope.write(':WAV:SOUR CHAN'+str(channel))

        # Get time scale and offset
        timescale = float(scope.query(':TIM:SCAL?'))
        timeoffset = float(scope.query(':TIM:OFFS?'))
        # Get voltage scale and offset
        voltscale = float(scope.query(':CHAN'+str(channel)+':SCAL?'))
        voltoffset = float(scope.query(':CHAN'+str(channel)+':OFFS?'))
        
        y_inc = float(scope.query(':WAVeform:YINCrement?'))
        y_ref = float(scope.query(':WAVeform:YREFerence?'))
        y_ori = float(scope.query(':WAVeform:YORigin?'))
        
        x_inc = float(scope.query(':WAVeform:XINCrement?'))
        x_ref = float(scope.query(':WAVeform:XREFerence?'))
        x_ori = float(scope.query(':WAVeform:XORigin?'))
        
        #print(scope.query(':WAVeform:PREamble?'))
        scope.write(':WAVeform:FORMat BYTE')
        
        #scope.write(':WAVeform:MODE RAW')
        scope.write(':WAVeform:MODE NORMAL')
        #rawdata = scope.query(':WAV:DATA? CHAN'+str(channel)+'\n').encode('ascii')[10:-1]
        scope.write(':WAV:DATA? CHAN'+str(channel)) #Request the data
        #rawdata = numpy.ones(1210)
        rawdata = scope.read_raw() #Read the block of data
        head = rawdata[:11]
        rawdata = rawdata[11:-1] #Drop the heading
        #print(rawdata[:20])
        #print(head)

        data_size = len(rawdata)

        scope.write(':RUN')
        scope.write(':KEY:FORCE')
        
        print('Data size:', data_size, "Sample rate:", sample_rate, "Mem. depth", mem_depth)

        

    data = numpy.frombuffer(rawdata, 'B').astype(float)
    #print(data.dtype)
    #print('raw data:',data[0:20])
    
    # Map data to actual voltages (from Cibo Mahto), first invert the data
    #data = data * -1 + 255
    # Now, we know from experimentation that the scope display range is actually
    # 30-229.  So shift by 130 - the voltage offset in counts, then scale to
    # get the actual voltage.
    #data = (data - 130.0 - voltoffset/voltscale*25) / 25 * voltscale
    #print('Shirriff:',((data[0:20]*-1 + 255) - 130.0 - voltoffset/voltscale*25) / 25 * voltscale)

    dt = timescale/50.
    #y_offs = voltoffset
    #y_inc = voltscale/25.
    #y_ref = 125.
    #y_hex = data
    #data = (y_ref - y_hex)*y_inc - y_offs
    #print('labview: ',(125. - data[0:20])*voltscale/25. - voltoffset)
    #print('offset:',voltoffset,'reference:',y_ref,'increment:',y_inc)
    
    data = (data - y_ori - y_ref) * y_inc
    #print('origin:',y_ori,'reference:',y_ref,'increment:',y_inc)
    #print('manual: ',data[0:20])

    # Now, generate a time axis.
    time = numpy.linspace(timeoffset - 6 * timescale, 
                          timeoffset + 6 * timescale, 
                          num=len(data))
    return time, data


