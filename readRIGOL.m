% Read data from vector "channel" list directly from memory of
%   a RIGOL oscilloscope via ni VISA
%   commands: SCPI (Standard Commands for Programmable Instruments)
%   http://int.rigol.com/File/TechDoc/20151218/MSO1000Z&DS1000Z_ProgrammingGuide_EN.pdf
%
% readRIGOL(dev_str,time_scale,channel,volt_scale,mem_depth)
%   dev_str:    address string for device
%   time_scale: time/div in seconds; if empty presettings are kept
%   channel:    vector list of channels
%   volt_scale: vector of voltages

% instrreset

function [t,ch,prop] = readRIGOL(dev_str,time_scale_set,channel,volt_scale_set,mem_depth_set,run_mode,ch_cpl_mode)
    arg_cnt = nargin;
    if arg_cnt<7
        ch_cpl_mode = 'DC'; %{AC|DC|GND}
    end
    if arg_cnt<6
        run_mode = true;
    end
    if arg_cnt<5
        mem_depth_set = 'AUTO';
    end
    if arg_cnt<4
        volt_scale_set = [];
    end
    if arg_cnt<3
        channel = 1;
    end
    if arg_cnt<2
        time_scale_set = [];
    end
    if arg_cnt<1
        dev_str = 'USB0::0x1AB1::0x04CE::DS1ZA171307030::INSTR';   
    end
    
    % Memory depth
    %   single channel {AUTO|12000|120000|1200000|12000000|24000000}
    %   two            {AUTO|6000|60000|600000|6000000|12000000}
    %   three/four     {AUTO|3000|30000|300000|3000000|6000000}
    % List of memory depth for {1;2;3/4} channels
    mem_lis = {'AUTO','12000','120000','1200000','12000000','24000000';...
               'AUTO','6000','60000','600000','6000000','12000000';...
               'AUTO','3000','30000','300000','3000000','6000000';...
               'AUTO','3000','30000','300000','3000000','6000000'};
    mem_lis = mem_lis(length(channel),:);
    mem_lis_num = cellfun(@(x) str2double(x),mem_lis);
    
    ch_disp_state = {'Off','On'};

    timeout = 20;
    ptns_bit = 1; %bit length per point
    max_pnts_p_buff = 4096; %512 1024 2048 4096
    out_buff_size = 512;
    head_offset = 12;
    head_start = 2;
    t_div_cnt = 12;
    wav_mode_set = 'RAW';
    
    buffer_size = max_pnts_p_buff*ptns_bit+head_offset;

    warning('error', 'instrument:fread:unsuccessfulRead')
    %[msgstr, msgid] = lastwarn;
    
    % Save all Osci Props
    prop = struct();
    prop.dev_str = dev_str;
    prop.time_scale_set = time_scale_set;
    prop.channel = channel;
    prop.volt_scale_set = volt_scale_set;
    prop.mem_depth_set = mem_depth_set;
    prop.run_mode = run_mode;
    prop.ch_cpl_mode = ch_cpl_mode;
    prop.mem_lis = mem_lis;
    prop.mem_lis_num = mem_lis_num;
    prop.timeout = timeout;
    prop.ptns_bit = ptns_bit;
    prop.max_pnts_p_buff = max_pnts_p_buff;
    prop.out_buff_size = out_buff_size;
    prop.head_offset = head_offset;
    prop.head_start = head_start;
    prop.t_div_cnt = t_div_cnt;
    prop.buffer_size = buffer_size;
    prop.wav_mode_set = wav_mode_set;

    % vinfo = instrhwinfo('visa');
    vs = visa('ni',prop.dev_str);
    vs.EOSMode = 'read';
    % bigger timeout for long mem
    vs.Timeout = timeout;
    vs.InputBufferSize = buffer_size;
    vs.OutputBufferSize = out_buff_size;

    % Open visa connection
    fopen(vs);

    % Get visa name
    name = query(vs,'*IDN?');
    name = name(1:end-1);
    prop.name = name;
    fprintf('Read oscilloscope "%s"\n',name);
    
    time_delay_mode = query(vs,':TIMebase:DELay:ENABle?');
    time_delay_mode = time_delay_mode(1:end-1);
    prop.time_delay_mode = time_delay_mode;
    fprintf('Delay mode %s\n',time_delay_mode)
    
    % Set the acquisition mode: {NORMal|AVERages|PEAK|HRESolution}
    fprintf(vs,':ACQuire:TYPE NORMal');
    %acq_type = query(vs,':ACQuire:TYPE?');
    
    % Memory Depth = Sample Rate x Waveform Length
    % Waveform Length is the product of the horizontal timebase,
    %   set by ':TIMebase[:MAIN]:SCALe' 
    %   times the number of grids in the horizontal direction on the screen (12 for DS1000Z)
    % Set or query the memory depth of the oscilloscope (namely the number of waveform
    %   points that can be stored in a single trigger sample). The default unit is pts (points).
    if ~isempty(mem_depth_set) && ischar(mem_depth_set)
        fprintf(vs,[':ACQuire:MDEPth ',mem_depth_set]);
    end
    % Set the memory depth to
    acq_mem_depth = query(vs,':ACQuire:MDEPth?');
    acq_mem_depth = acq_mem_depth(1:end-1);
    prop.acq_mdepth = acq_mem_depth;
    
    if ~isempty(time_scale_set)
        % Set the mode of the horizontal timebase to YT (MAIN) {MAIN|XY|ROLL} 
        fprintf(vs,':TIMebase:MODE MAIN');
        % Main timebase scale. The default unit is s/div.
        % Set the main timebase scale in 1-2-5 steps to x s/div (200e-6)
        fprintf(vs,[':TIMebase:MAIN:SCALe ',num2str(time_scale_set)]);
    end
    
    % Get current time/division setting = <Time_Div> in seconds ':TIM:SCAL?'
    time_scale = query(vs,':TIMebase:MAIN:SCALe?');
    time_scale = str2double(time_scale(1:end-1));
    prop.time_scale = time_scale;

    % Get acquisition sampling rate
    acq_srate = query(vs,':ACQuire:SRATe?');
    acq_srate = str2double(acq_srate(1:end-1));
    prop.acq_srate = acq_srate;
    % NORMAL MODE: x/t increment = time_scale/100
    % RAW MODE: x/t increment = 1/acq_srate
    % XREFerence: LEFT END!
    dt = 1/acq_srate;
    prop.dt = dt;
    ptns_cnt = time_scale*t_div_cnt*acq_srate;
    prop.ptns_cnt = ptns_cnt;
    
    
    % fprintf(vs,[':TIMebase:MAIN:OFFS ',num2str(ptns_cnt*dt/2)]);
    
    % Get current trigger time offset = <Time_Offset> in seconds ':TIM:OFFS?'
    time_offset = query(vs,':TIMebase:MAIN:OFFS?');
    time_offset = str2double(time_offset(1:end-1));
    prop.time_offset = time_offset;
    
    fprintf('Mem %s: %.1e points at %.1e Sa/s\n',acq_mem_depth,ptns_cnt,acq_srate);
    fprintf('t-axis: %.2e s/div and %.2e s offset\n',time_scale,time_offset);
    
    % Calculate waiting time
    wait_time = time_scale*(t_div_cnt+1);
    prop.wait_time = wait_time;
    
    if run_mode
        fprintf('Start data acquisition and wait %.2e seconds\n',wait_time)
        % Start data acquisition.
        fprintf(vs,':RUN');
        tm = tic;
        pause(wait_time);
        % Set the instrument to STOP state (you can only read
            % the waveform data in the internal memory when the
            % oscilloscope is in STOP state)
        fprintf(vs,':STOP');
        tm = toc(tm);
        fprintf('Stop acquisition after %.3e seconds\n',tm)
    end

    ch_disp = false(4,1);
    for j=1:4
        % Query the coupling mode of the specified channel {{1|ON}|{0|OFF}}
        ch_disp_buf = query(vs,[':CHANnel',num2str(j),':DISPlay?']);
        ch_disp(j) = logical(str2double(ch_disp_buf(1:end-1)));
        fprintf('CH%i is in mode "%s"\n',j,ch_disp_state{ch_disp(j)+1});
    end
    
    cnt_ch = length(channel);
    prop.cnt_ch = cnt_ch;
    
    for j=1:cnt_ch
        prop.ch(j) = channel(j);
        if ~ch_disp(channel(j))
            % Enable CH
            fprintf(vs,[':CHANnel',num2str(channel(j)),':DISPlay ON']);
            ch_disp(channel(j)) = true;
        end
        % Set the coupling mode of the specified channel {AC|DC|GND}
        fprintf(vs,[':CHANnel',num2str(channel(j)),':COUPling ',ch_cpl_mode]);
        ch_cpl_mode = query(vs,[':CHANnel',num2str(channel(j)),':COUPling?']);
        ch_cpl_mode = ch_cpl_mode(1:end-1);
        prop.ch_cpl_mode(j,:) = ch_cpl_mode;
        
        if (length(volt_scale_set)>=j)
            % Set the vertical scale of CH(channel) to (volt_scale)V
            fprintf(vs,[':CHANnel',num2str(channel(j)),':SCALe ',num2str(volt_scale_set(j))]);
        end
        % Get Channel scale voltage/div = <Volts_Div>
        volt_scale = query(vs,[':CHANnel',num2str(channel(j)),':SCAL?']);
        volt_scale = str2double(volt_scale(1:end-1));
        prop.volt_scale(j) = volt_scale;
        % Return Channel vertical voltage offset = <Vert_Offset>
        %fprintf(vs,':CHANnel2:OFFS ')
        volt_offset = query(vs,[':CHANnel',num2str(channel(j)),':OFFS?']);
        volt_offset = str2double(volt_offset(1:end-1));
        prop.volt_offset(j) = volt_offset;
        
        fprintf('CH%i y-axis: %.2e V/div and %.2e V offset\n',channel(j),volt_scale,volt_offset)
        
        % Set the channel source to CH1
        fprintf(vs,[':WAV:SOUR CHAN',num2str(channel(j))]);
        % Set the waveform reading mode to RAW
        % Attention: conversions are different in NORMAL mode
        
        % fprintf(vs,':WAV:MODE RAW');
        % fprintf(vs,':WAV:MODE NORMAL');
        fprintf(vs,[':WAV:MODE ',wav_mode_set]);
        
        wav_mode = query(vs,':WAV:MODE?');
        wav_mode = wav_mode(1:end-1);
        prop.wav_mode = wav_mode;
        
        % Set the return format of the waveform data to BYTE/WORD/ASCii
        fprintf(vs,':WAV:FORM BYTE');
        
        % waveform parameters 
        y_inc = query(vs,':WAVeform:YINCrement?');
        y_inc = str2double(y_inc(1:end-1));
        prop.y_inc(j) = y_inc;
        y_ref = query(vs,':WAVeform:YREFerence?');
        y_ref = str2double(y_ref(1:end-1));
        prop.y_ref(j) = y_ref;
        % RAW: YORigin Verticalscale currently selected
        y_ori = query(vs,':WAVeform:YORigin?');
        y_ori = str2double(y_ori(1:end-1));
        prop.y_ori(j) = y_ori;
        
        % RAW: XINCrement = 1/SampleRate
        x_inc = query(vs,':WAVeform:XINCrement?');
        x_inc = str2double(x_inc(1:end-1));
        prop.x_inc(j) = x_inc;
        x_ref = query(vs,':WAVeform:XREFerence?');
        x_ref = str2double(x_ref(1:end-1));
        prop.x_ref(j) = x_ref;
        x_ori = query(vs,':WAVeform:XORigin?');
        x_ori = str2double(x_ori(1:end-1));
        prop.x_ori(j) = x_ori;

        %    "<format>,<type>,<points>,<count>,...
        %     <xincrement>,<xorigin>,<xreference>,...
        %     <yincrement>,<yorigin>,<yreference>"
        % <format>: 0 (BYTE), 1 (WORD) or 2 (ASC). 
        % <type>: 0 (NORMal), 1 (MAXimum) or 2 (RAW). 
        % <points>: 1..12000000. After memory depth option 1..24000000. 
        % <count>: the number of averages in the average sample mode and 1 in other modes. 
        % <xincrement>: the time difference between two neighboring points in the X direction. 
        % <xorigin>: the start time of the waveform data in the X direction. 
        % <xreference>: the reference time of the data point in the X direction. 
        % <yincrement>: the waveform increment in the Y direction. 
        % <yorigin>: the vertical offset relative to the "Vertical Reference Position" in the Y direction. 
        % <yreference>: the vertical reference position in the Y direction.
        wav_parm = query(vs,':WAVeform:PREamble?');
        wav_parm = strsplit(wav_parm(1:end-1),',');
        prop.wav_parm(j,:) = wav_parm;
        
        
        % Convert data
        % :WAV:MODE NORMAL: y increment = volt_scale/25
        % A(V) = [(240 -<Raw_Byte> ) * (<Volts_Div> / 25) - [(<Vert_Offset> + <Volts_Div> * 4.6)]] 
        % voltage = @(x) (240-x).*(volt_scale/25) - (volt_offset+volt_scale*4.6);
        % :WAV:MODE RAW: y increment = volt_scale
        
        % (0x8E - YORigin - YREFerence) x YINCrement
        voltage = @(x)  (x - y_ori - y_ref).*y_inc;
        prop.voltage{j} = voltage;
        
        %disp(ptns_cnt/str2double(wav_parm(3)))

        tt = tic;
        data = [];
        range = [1:max_pnts_p_buff:ptns_cnt,ptns_cnt+1];
        for i=1:length(range)-1
            buf_start = range(i);
            buf_stop = range(i+1)-1;
            
            fprintf('Read CH%i: memory block: %i to %i\n',channel(j),buf_start,buf_stop)

            % Set the start point of waveform data reading to the first waveform point
            fprintf(vs,[':WAV:STAR ',num2str(buf_start)]);
            % Set the stop point of waveform data reading to the 120000th waveform point (the last point)
            fprintf(vs,[':WAV:STOP ',num2str(buf_stop)]);
            % Read the waveform data in the internal memory (all the points)
            fprintf(vs,':WAV:DATA?');
            try
                % Readout data from oscilloscope's internal memory
                [buff,buff_len]= fread(vs,buffer_size);
                %rawdata = cast(query(vs,':WAV:DATA?'),'uint8');
            catch me
                if strcmp(me.identifier,'instrument:fread:unsuccessfulRead')
                    if exist('buff','var')
                        if i>1
                            break;
                        end
                        head_seq = char(buff(1:head_end));
                        fprintf('Mem empty: "%s"\n',head_seq);
                    else
                        fprintf('Mem empty: no trace? trigger? "%s"\n',me.identifier);
                        fclose(vs);
                        delete(vs);
                        clear('vs');
                        lastwarn('');
                        t=[]; ch=[];
                        return
                    end
                else
                    instrreset;
                    rethrow(me);
                end
            end

            head_size = str2double(char(buff(head_start)));
            head_end  = head_start+head_size;
            data_pnts = str2double(char(buff(head_start+1:head_end)));
            data_seq = buff(head_end+1:end-1);

            data = [data;double(data_seq)];
        end
        data_size = length(data);
        fprintf('Points acquired: %i\n',data_size)

        ch(:,j) = voltage(data);
    end
    fprintf('Transfer duration: %f\n',toc(tt));
    
    if run_mode
        fprintf(vs,':RUN');
    end
    
    % Calculate time
    if strcmp(wav_mode,'RAW')
        %T(s) = (<PT_Num> - 1) * ( <Time_Div> / 50) - [(<Time_Div> * 6) - <Time_Offset> ]
        % point2time =@(pnts) (pnts-1).*(timescale/50)-(timescale*6-timeoffset);
        %T(s) = <Time_Offset> -[ ( <Points>  - 10) / (1 / (2*<Samp_Rate> )]
        % point2time =@(pnts) timeoffset - ( (pnts-10)./(1/(2*acq_srate)));
        % :WAV:MODE RAW:
        point2time =@(pnts) pnts./acq_srate + time_offset;
    else
        point2time =@(pnts) pnts./(time_scale/100) + time_offset;
    end
    prop.point2time = point2time;
    
    t = point2time((0:(length(ch)-1)));
    
    prop.ch_disp = ch_disp;

    fclose(vs);
    delete(vs);
    clear('vs');

    lastwarn('');
end

% waveform_length = time_scale*div_cnt;
% mem_depth       = acq_srate*waveform_length;

% :TIMebase[:MAIN]:OFFSet
% RUN: 
%     (-0.5 x MemDepth/SampleRate) to 1s 
%         (when the horizontal timebase is less than 200ms/div)
%     (-0.5 x MemDepth/SampleRate) to (10 x MainScale) 
%         (when the horizontal timebase is greater than 
%          or equal to 200ms/div, namely the "Slow Sweep" mode)
% STOP: 
%     (-MemDepth/SampleRate) to (1s + 0.5 x MemDepth/SampleRate)