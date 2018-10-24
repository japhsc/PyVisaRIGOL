#!/usr/bin/env python

"""
Current version by Jan-Philipp Schoeder

Major improvements: Yanis Taege and Fritz Bayer

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
import time as tme

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
        self.query_delay = self.inst.query_delay
    def __enter__(self):
        #return(self.inst)
        return(self)
    def __exit__(self, exc_type, exc, exc_tb):
        self.inst.close()
    
    def query(self,message):
        data = self.inst.query(message)[:-1]
        #ret = self.write(message)
        #if self.query_delay > 0.0:
        #    tme.sleep(self.query_delay)
        #data = self.inst.read()[:-1]
        #if not ret[1]==0:
        #    err = self.inst.query('SYST:ERR?')
        #    print('QUERY: "%s" "%s"' % (message, err))
        #    print(':'.join(str(ord(x)) for x in data))
        return(data)
    
    def query_raw(self,message):
        #return(self.inst.query_binary_values(command, datatype='b', is_big_endian=True))
        self.write(message) #Request the data
        rawdata = self.read_raw() #Read the block of data
        head = rawdata[:11]
        rawdata = rawdata[11:-1] #Drop the heading
        return head,rawdata
    
    def read_raw(self):
        return(self.inst.read_raw()) #Read block of data
    
    def write(self,message):
        ret = self.inst.write(message)
        
        #err = self.inst.query('SYST:ERR?')
        #print('WRITE: "%s" "%s"' % (message, err))
        
        #if not ret[1]==0:
        #    print('WRITE: "%s"' % message, ret)
        return(ret)


def list_device():
    if os.name == 'posix':
        rm = visa.ResourceManager('@py')
    elif os.name == 'nt':
        rm = visa.ResourceManager('@ni')
    else:
        rm = visa.ResourceManager()
    instruments = rm.list_resources()
    usb = list(filter(lambda x: 'USB' in x, instruments))
    return usb


def read(adr, channels=[1]):
    if os.name == 'posix':
        rm = visa.ResourceManager('@py')
    elif os.name == 'nt':
        rm = visa.ResourceManager('@ni')
    else:
        rm = visa.ResourceManager()
        
    #with Instrument(rm, adr, timeout=2000, chunk_size=1024000) as scope:
    with Instrument(rm, adr) as scope:
        #print(scope.query('*IDN?'))
        
        # Lock keys
        # scope.write(':SYSTem:LOCKed 1')

        #scope.write(':ACQuire:MDEPth 600000')
        mem_depth = scope.query(':ACQuire:MDEPth?')
        sample_rate = scope.query(':ACQuire:SRATe?')
        #scope.write(':CHANnel'+str(channel)+':COUPling '+ch_cpl_mode)
        scope.write(':SINGle') 
        # scope.write(':RUN')

        trigger = 'WAIT'
        while trigger.find('STOP') < 0:
            trigger = scope.query(":TRIGger:STATus?")
            tme.sleep(0.01)

        # Get time scale and offset
        timescale = float(scope.query(':TIM:SCAL?'))
        timeoffset = float(scope.query(':TIM:OFFS?'))
        print('timescale %.3f \t timeoffset %.3f' % (timescale, timeoffset))

        #print(scope.query(':WAVeform:PREamble?'))
        scope.write(':WAVeform:FORMat BYTE')
        #scope.write(':WAVeform:MODE RAW')
        scope.write(':WAVeform:MODE NORMAL')
        
        # Record data of a single trigger
        #scope.write(':STOP')
        data = [];
        rawdata = dict();
        for idc, channel in enumerate(channels):
            scope.write(':WAV:SOUR CHAN'+str(channel))
            
            cpl = scope.query(':CHANnel'+str(channel)+':COUPling?')
            
            #x_inc = float(scope.query(':WAVeform:XINCrement?'))
            #x_ref = float(scope.query(':WAVeform:XREFerence?'))
            #x_ori = float(scope.query(':WAVeform:XORigin?'))
            
            # Get voltage scale and offset
            voltscale = float(scope.query(':CHAN'+str(channel)+':SCAL?'))
            voltoffset = float(scope.query(':CHAN'+str(channel)+':OFFS?'))
            print('voltscale %.3f \t voltoffset %.3f' % (voltscale, voltoffset))

            y_inc = float(scope.query(':WAVeform:YINCrement?'))
            y_ref = float(scope.query(':WAVeform:YREFerence?'))
            y_ori = float(scope.query(':WAVeform:YORigin?'))
            print('y_inc = %.2f \t y_ref = %.2f \t y_ori = %.2f' % (y_inc, y_ref, y_ori))
            
            _,rawdata['channel%d'%channel] = scope.query_raw(':WAV:DATA? CHAN'+str(channel))
            data_size = len(rawdata['channel%d'%channel])
            data.append(numpy.frombuffer(rawdata['channel%d'%channel], 'B').astype(float))
            data[-1] = (data[-1] - y_ori - y_ref) * y_inc
            print('CH%d(%s): data size: %d; sampl.rate: %s; Mem.depth: %s' % (channel,cpl,data_size,sample_rate,mem_depth))

        scope.write(':RUN') # WHILE OPC??
        # Unlock keys
        # scope.write(':SYSTem:LOCKed 0')

    # Generate a time axis
    if len(data)>0:
        dt = timescale*12./float(len(data[-1]))
    else:
        dt = 0.
    time = numpy.linspace(timeoffset - 6 * timescale, 
                          timeoffset + 6 * timescale, 
                          num=data_size)
    return time, data, dt


