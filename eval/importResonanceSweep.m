function [time, traces, dTraces] = importResonanceSweep(filename, nChannels)  
% importResonanceSweep Import time and traces of the resonance sweeps acquired
% using readOsciTrace
% [time, traces, dTraces] = importResonanceSweep(filename, nChannels) returns 
% time and channel vectors of the averaged signal aquired by the readOsciTrace
% script. It automatically averages all traces in a channel and returns the 
% mean value traces(:,channelID) over time, and the standard error 
% dTraces(:,channelID) for each time point.
% OUTPUT:
%   double time   : 	time vector, dim = length(time)
%   double trace  : 	averaged traces for each channel, 
%  	 					dim = (length(time) * nChannels)
%   double dTrace : 	standard error for of traces for each channel, 
%  	 					dim = (length(time) * nChannels)
% PARAMS:
%   filename 	  : 	filename of CSV to import
%   int nChannels : 	number of acquired channels
%
% Author: (2018) Yanis Taege

    inData = csvread(filename, 1, 0);
    
    time = inData(:,1);
    traces = zeros(length(time), nChannels);
    dTraces = zeros(size(traces));
  
    for idc = 1:nChannels
        traces(:, idc) = mean(inData(:,idc:nChannels:end), 2);
        dTraces(:, idc) = std(inData(:,idc:nChannels:end), 0, 2) / sqrt(length(time));
    end
    
   
end