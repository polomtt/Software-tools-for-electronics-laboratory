                       function [ud_handle] =  Scan_3D_detector2_g
%% NOTE
%  1) motore sinistra -> asse x, motore destra -> asse y

    global h_Ctrl;
    global timeout;
    timeout = 10;
    
     
        global voltage_string
        voltage_string=[10 25 50 75 100]
        global R
        R=2e6
        global det_number
        det_number= 1;
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Inizializza interfaccia APT %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    % apre una question dialog box per l'inizializzazione dell'interfaccia
    % APT
    button = questdlg('About to launch the APT window - do not run if another APT window is open.  Do you want to open the APT window?', ...
                   'Launch APT window', 'Yes', 'No', 'No');
    if isempty(button)
        return
    elseif len
        gth(button) == 2
        return
    end

    % Parametri
    ParamSet = 'FIRST_STEPS'; % Nome del setting gia'  inizializzato usando l'APT User program

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Crea un oggetto figura grafica %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    fig = figure('Position', [5 35 1272 912], 'HandleVisibility', 'on', 'IntegerHandle', 'off', ...
                'Name', 'APT Interface', 'NumberTitle', 'off', 'DeleteFcn', 'APT_figure_delete_fcn');

    set(fig, 'Name', ['APT Interface, Handle Number ' num2str(fig.Number, '%2.20f')]);

    % Crea il controllo ActiveX sulla figura
    % Consulta le funzioni actxcontrolselect, actxcontrollist, methodsview
    h_Ctrl = actxcontrol('MG17SYSTEM.MG17SystemCtrl.1', [0 0 100 100], fig);

    % Inizia il controllo
    h_Ctrl.StartCtrl;

    % Aggiorna i dati dell'utente
    ud.h_Ctrl = h_Ctrl;
    set(fig, 'UserData', ud);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Configura i motori (MOTORE SINISTRA X;  MOTORE DESTRA Y) %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    [temp, num_motor] = h_Ctrl.GetNumHWUnits(6, 0);
    
    %controllo numero motori
    if num_motor ~= 2  
        fprintf(['Check number of motors (Found' num2str(num_motor) ')!\n']);
        return
    end

    % Ottengo il numero seriale del primo (index 0) e del secondo dispositivo (index1)
    [temp, SN_motor{1}] = h_Ctrl.GetHWSerialNum(6, 0, 0); 
    [temp, SN_motor{2}] = h_Ctrl.GetHWSerialNum(6, 1, 0); 
    
    %stampa il seriale dei motori
    SN_motor 
        global pos_partenza_Y1;
        global pos_partenza_X1;
       
    % Crea interfaccia grafica dei motori e li configura
    h_motor_Left = actxcontrol('MGMOTOR.MGMotorCtrl.1', [0 410 300 200], fig);
    SetMotor(h_motor_Left, 83815665, ParamSet);
    h_motor_Right = actxcontrol('MGMOTOR.MGMotorCtrl.1', [300 410 300 200], fig);
    SetMotor(h_motor_Right, 83815649, ParamSet);

    % Aggiorna i dati utente
    ud.h_motor_Left = h_motor_Left;
    ud.h_motor_Right = h_motor_Right;
    set(fig, 'UserData', ud);
    ud_handle = ud;

    %acquisisce la posizione iniziale dei motori come valore assoluto
    %global pos_partenza_X1;
    %pos_partenza_X1 = ud.h_motor_Left.GetPosition_Position(0)
    %global pos_partenza_Y1;
    %pos_partenza_Y1 = ud.h_motor_Right.GetPosition_Position(0)
    
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Crea pulsante per fermare APT %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    uicontrol(fig, 'Style', 'pushbutton', 'String', 'Stop APT interface',...
        'Position', [0 300 120 20],...
        'Callback',@Stop_APT_interface);        
    
    function Stop_APT_interface(~,event)
        APT_figure_delete_fcn(ud_handle);
    end

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Configurazione grafica dell'interfaccia di controllo utente  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    % Label dX,[um]
    uicontrol(fig,'Style','text',...
                'String','dX,[um] = ',...
                'Position',[200 330 50 20]); 
            
    % Label dY,[um]
    uicontrol(fig,'Style','text',...
                'String','dY,[um] = ',...
                'Position',[200 300 50 20]); 
            
    % Label step,[um]
    uicontrol(fig,'Style','text',...
                'String','step,[um] = ',...
                'Position',[175 270 75 20]);  
            
    % Label time_scale,[s]
    uicontrol(fig,'Style','text',...
                'String','risoluzione temporale[s/tacca] = ',...
                'Position',[70 240 190 20]);  
            
            
    % String default dY
    handle_Scan_options.dX = uicontrol(fig, 'Style','edit',...
                'String','40',...
                'Position',[250 330 50 20], 'Callback',@dX_Callback);   
            
    % String default dY
    handle_Scan_options.dY = uicontrol(fig, 'Style','edit',...
                'String','40',...
                'Position',[250 300 50 20], 'Callback',@dY_Callback);  
            
    % String default time_scale
    handle_Scan_options.time_scale = uicontrol(fig, 'Style','edit',...
                'String','10e-9',...
                'Position',[255 240 50 20], 'Callback', @step_Callback);  
            
    % String default step
    handle_Scan_options.step = uicontrol(fig, 'Style','edit',...
                'String','10',...
                'Position',[250 270 50 20], 'Callback', @step_Callback);  
            

    handle_Scan_options.btnRead =  uicontrol(fig, 'Style', 'pushbutton', 'String', 'Read values',...
                'Position', [350 300 120 20],...
                'Callback', @Prepare_scan);        

    %impostazioni manuali per configurare la scansione
    guidata(fig,handle_Scan_options)
       
    function dX_Callback(src, evt)
        handle_Scan_options = guidata(src);
    end 


    function dY_Callback(src, evt)
        handle_Scan_options = guidata(src);
    end


    function step_Callback(src, evt)
        handle_Scan_options = guidata(src);
    end

   
    function Prepare_scan(src, evt) 
        handle_Scan_options = guidata(src);


        pos_partenza_X1 = ud.h_motor_Left.GetPosition_Position(0)
      
        pos_partenza_Y1 = ud.h_motor_Right.GetPosition_Position(0)    
        
        pos_partenza_X1
        pos_partenza_Y1
        
        Value_dX   = str2num(get(handle_Scan_options.dX,'String'))
        Value_dY   = str2num(get(handle_Scan_options.dY,'String'))
        Value_step = str2num(get(handle_Scan_options.step,'String'))
        
 
        if  (Value_dX<0)||(Value_dX>12000)
            questdlg('Put proper values X', 'Warning', 'Ok','Ok');
        end
        
        if  (Value_dY<0)||(Value_dY>12000)
            questdlg('Put proper values Y', 'Warning', 'Ok','Ok');
        end
        
        if rem(Value_step,0.5)~=0
            questdlg('Make step value multiple to 0.5um', 'Warning', 'Ok','Ok');
        end
        
    end 

        
    %durante la configurazione salva la posizione iniziale dei motori
    %come rierimento per effettuare il primo spostamento dX dY
    %global Current_X;
    %Current_X = ud.h_motor_Left.GetPosition_Position(0);
    %global Current_Y;
    %Current_Y = ud.h_motor_Right.GetPosition_Position(0);
        
   

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% scala tempi acquisizione %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    %inizializzazione  scopio
    [deviceObj_r] = initialize_oscilloscope_g;

        
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%       
%% Funzione Make_scan2  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%

         
    %creazione pulsante di avvio Make_scan2   
    uicontrol(fig, 'Style', 'pushbutton', 'String', 'Make scan 2',...
              'Position', [450 370 120 20],...
              'Callback', @Make_scan2);
          
    %implementazione funzione di scansione       
    function Make_scan2(hObject, eventdata, handles)   
        
        reply=0;
        
        %azzero il file tempo
        formichiere='';
        save('Data/temp.txt', 'formichiere', '-ASCII'); 
        time=fix(clock);
        save('Data/temp2.txt', 'time', '-ASCII', '-append');
        
        % controlla se la cartella Data esiste altrimenti la crea
        if exist('Data','dir')~=7 
           mkdir('Data');
        end   
        
        if exist('Data2/temp.txt','file') 
           delete('Data2/temp.txt');
        end      
        
        pause(1);
        
        %Calcola la matrice dimensione: divide dX, dY e step di 1000 in
        %modo da passare da decimetri di um (unita'  di misura dei motori) a millimetri
        
        Value_dX   = str2num(get(handle_Scan_options.dX,'String'))/1000
        Value_dY   = str2num(get(handle_Scan_options.dY,'String'))/1000
        Value_step = str2num(get(handle_Scan_options.step,'String'))/1000
        
        % (10tacche perchè la get_wave vuole Horizontal_Time_Per_Record)
        time_scale=str2num(get(handle_Scan_options.time_scale,'String'))*10
        
        %L'annomontare di step scannarizzati e' doppio rispetto a quanto
        %richiesto dall'utente: infatti il punto zero (punto d'inizio dei
        %motori) e' ora considerato al centro di una matrice di dimensioni
        %2*dX 2*dY con stesso step.
        %Arrotondo (round) all'intero piu' vicino in modo da evitare numeri
        %virgola mobile 
        
        m = round(Value_dY/Value_step)*2+1; 
        n = round(Value_dX/Value_step)*2+1;
        
        %gcf = gestione figura corrente
        %gca = gestione asse corrente
        get(gcf);  
        
        set(gca, 'Units','points','View', [-120 60],...
                'Position',[550,200,350,320],...                                  %%[left bottom width height]
                'XLim',[0,Value_dX*m],'YLim',[0,Value_dY*n], 'ZLim', [0, 100],... %%xlim e y lim tengono gia conto di DX e DY raddoppiati
                'PlotBoxAspectRatio',[1,1,1],'FontSize',8,...
                'Box', 'on'); %, 'CameraTarget', [-120, 60]);
    
        
        %Mi sposto in (N,M)=(1,1) ossia in (x',y')=(-DX,-DY) prendendo come
        %riferimento assi cartesiani con l'origine posizionata in (DX,DY)
        %della griglia (assumendo assi cartesiani X e Y con origine nell'angolo in basso a sinistra della griglia creata)
         
        %Current_X = ud.h_motor_Left.GetPosition_Position(0)
        
        %salvo la posizione di inizio riga per dare un riferimento esatto
        %al motore su dove ripartire nella riga successiva(azzero ritardo
        %cumulato dal motore lungo una riga)
        
        %pos_iniziale_X=(Current_X+Value_dX/(-1));
        %pos_iniziale_X=(pos_partenza_X1+Value_dX/(-1));
        pos_iniziale_X=(pos_partenza_X1);
        pos_iniziale_X
%         ud.h_motor_Left.SetAbsMovePos(0,pos_iniziale_X);
%                     
%         output = ud.h_motor_Left.MoveAbsolute(0,1==0);
%                     
%         t1 = clock; % current time
%         while(etime(clock,t1)<timeout) 
%             % wait while the motor is active; timeout to avoid dead loop
%             s = ud.h_motor_Left.GetStatusBits_Bits(0);
%             if (IsMoving(s) == 0)
%                 break;
%             end
%             pause(1);
%         end              

        %stessa cosa per il motore su Y
        %Current_Y = ud.h_motor_Right.GetPosition_Position(0)
        
        %pos_iniziale_Y=(Current_Y+Value_dY/(-1));
        %pos_iniziale_Y=(pos_partenza_Y1+Value_dY/(-1));
        pos_iniziale_Y=(pos_partenza_Y1);
        pos_iniziale_Y
%         ud.h_motor_Right.SetAbsMovePos(0,pos_iniziale_Y);
% 
%         output = ud.h_motor_Right.MoveAbsolute(0,1==0);
%          
%         %impongo una condizione temporale sulla posizione per assicurarmi
%         %che il motore si sia portato nella posizione voluta
%         %(minimizzo il ritardo del motore dadogli più tempo
%         t1 = clock; % tempo corrente
%         
%         while(etime(clock,t1)<timeout) 
%             %finchè il motore è in movimento non esco dal loop e aspetto
%             %che abbia raggiunto la posizione voluta
%             s = ud.h_motor_Right.GetStatusBits_Bits(0);
%             if (IsMoving(s) == 0)
%                 break;
%             end
%             pause(1);
%         end                        

        for V=1:length(voltage_string)
         
        [current,voltage]= inizialize_keithley(voltage_string(V),R);

        %creo matrici (m,n) vuote in cui saranno salati i dati
        Mean_value = zeros(m,n);       %  ???? 
        Mean_value_area = zeros(m,n);  %(Ch1) output
        Mean_value_max = zeros(m,n);   %(Ch1) output
        Mean_value_max2 = zeros(m,n);  %(Ch3) reference

        scrsz = get(0,'ScreenSize')

        figure('Position',[1 scrsz(4)/2 scrsz(3)/2 scrsz(4)/2])

        subplot(2,4,3) % first subplot    ?????
        fig = bar3(Mean_value);         %crea grafico 3d barre              
        set(gca,'ZTick',[0:5:100]);     %gestione dell'asse della figura corrente     
       
        close
        % m - corrisponde a asse Y
        % n - corrisponde a asse X

        %schermata di spegnimento del laser per cofiguare reference
%         I=figure(1)
%         immagine=(imread('spegni.jpg'));
%         g=imshow(immagine)
%         h = uicontrol('Position',[20 20 200 40],'String','Continue',...
%                       'Callback','uiresume(gcbf)');
%         disp('switch off the pulse generator channel');
%         uiwait(gcf); 
%         close(I)
% 
%         %
%         [wave,assex]=get_wave2_g(deviceObj_r,'noise',time_scale);
% 
%         %%schermata di accensione del laser per cofiguare reference
%         I=figure(1)
%         immagine=(imread('accendi.jpg'));
%         g=imshow(immagine)
%         h = uicontrol('Position',[20 20 200 40],'String','Continue',...
%                       'Callback','uiresume(gcbf)');
%         disp('switch off the pulse generator channel');
%         uiwait(gcf); 
%         close(I)

     %lo tengo per compatibilità passate a cancellazione rumore
     [wave,assex]=get_wave2(deviceObj_r,'noise',time_scale);


        
        %ciclo di acquisizione dei dati sulla scansione
        for i=1:m
            for j=1:n % scorriamo lungo l'asse delle X
                    % acquisisce i dati
                    nomefile=strcat('scan_Y-',num2str(i),'scan_X-',num2str(j),'.txt');               

                    %funzione get wave che ritorna i valori di area, max,
                    %max 2 ad ogni passo
                    [Mean_value_area(i,j),Mean_value_max(i,j),Mean_value_max2(i,j),waveform_new]= get_wave_g(deviceObj_r,nomefile,time_scale);
                    
                    %salvataggi ineteredi aggionati ad ogni step
                    temporary_solution(1) = j;
                    temporary_solution(2) = i;
                    temporary_solution(3) = Mean_value_area(i,j);
                    temporary_solution(4) = Mean_value_max(i,j);
                    temporary_solution(5) = Mean_value_max2(i,j);                   
                    
                    save('Data/temp.txt', 'temporary_solution', '-ASCII', '-append');
                    save('Data/temp2.txt', 'temporary_solution', '-ASCII', '-append');

                    % Creiamo il grafico dei dati con barre di colore
                    % corrispondente alla loro altezza usando dubbed
                    
                    %grafico area
                    subplot(2,4,2) 
                    Mean_value_mod = Mean_value_area;
                    plot_handle = bar3(Mean_value_mod);  
           
                    for k = 1:n                         % ciclo che va riga per riga
                    zdata = ones(6*m,4);                % crea un array vuoto di colormap
                    counter = 1;

                        for l = 0:6:(6*m-6)             % ciclo da 0 a (m-1)*6 con step 6 
                            % vogliamo cambiare colormap 
                            zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
                            % prendiamo  6 righe di zdata e assegniamo loro Mean_value_mod
                            counter = counter+1;
                        end
                        set(plot_handle(k),'Cdata',zdata);  % Cdata e' responsabile del colore della mappa
                    end
                   
                    title('area')
                    
                    %grafico max   
                    subplot(2,4,3) 
                    Mean_value_mod = Mean_value_max;
                    plot_handle = bar3(Mean_value_mod);         
                    
                    for k = 1:n                         
                        zdata = ones(6*m,4);            
                        counter = 1;

                        for l = 0:6:(6*m-6)                      
                            zdata(l+1:l+6,:) = Mean_value_mod(counter,k);                           
                            counter = counter+1;
                        end
                        
                        set(plot_handle(k),'Cdata',zdata);  
                    end
                           
                    title('Max')  
                         
                    %grafico max2     
                    subplot(2,4,4) 
                    Mean_value_mod = Mean_value_max2;
                    plot_handle = bar3(Mean_value_mod);  
           
                    for k = 1:n                        
                        zdata = ones(6*m,4);           
                        counter = 1;

                        for l = 0:6:(6*m-6)                                       
                            zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
                            counter = counter+1;
                        end
                        
                        set(plot_handle(k),'Cdata',zdata); 
                    end 
                        
                    title('Max2')  
             
                    %grafico segnale istantaneo
                    subplot(2,4,7) 
                    plot(assex,waveform_new)
                    title('istantaneo')
                    
                    %grafico segnale reference
                    subplot(2,4,8)
                    plot(assex,wave)
                    title('reference') 
                    
                    % proseguiamo al prossimo punto d'acquisizione sulla
                    % stessa riga quando entrambi i motori sono fermi
                    
                    wait_stop(h_motor_Right)
                    wait_stop(h_motor_Left)
                    %pause(1); %PROVA PER ELIMINARE RITARDO
                    
                    %sposto il motore di uno step lungo l'asse X
                    %Current_X = ud.h_motor_Left.GetPosition_Position(0)
                    %x_desiderata=pos_iniziale_X+j*Value_step
                    
                    %uso spostemento assoluto per indicargli una posizione
                    %essata da raggiungere (limito errore)
                    ud.h_motor_Left.SetAbsMovePos(0,(pos_iniziale_X+j*Value_step));
                    output = ud.h_motor_Left.MoveAbsolute(0,1==0);
                    
                    t1 = clock;
                    while(etime(clock,t1)<timeout) 
                        s = ud.h_motor_Left.GetStatusBits_Bits(0);
                        if (IsMoving(s) == 0)
                            break;
                        end
                        pause(1);
                    end

pause(0.25);
            end  %fine ciclo j (ho finito di scorrere tutta la riga X)
                      
            %quando siamo a fine riga, attendiamo che entrambi i motori siano fermi 
            %dopodiche' torniamo all'inizio di quella successiva
            wait_stop(h_motor_Right)
            wait_stop(h_motor_Left)
   
pause(0.5);         
            %Current_X = ud.h_motor_Left.GetPosition_Position(0)
            ud.h_motor_Left.SetAbsMovePos(0,pos_iniziale_X);
           
            output = ud.h_motor_Left.MoveAbsolute(0,1==0);
                    
            t1 = clock; 
            while(etime(clock,t1)<timeout) 
                s = ud.h_motor_Left.GetStatusBits_Bits(0);
                if (IsMoving(s) == 0)
                    break;
                end
                pause(1);
            end     
            
            %attendo nuovamente entrambi i motori siano fermi
            wait_stop(h_motor_Right)
            wait_stop(h_motor_Left)
            pause(1);

            % muoviamo il motore di destra (Asse y) sulla riga successiva
            %Current_Y = ud.h_motor_Right.GetPosition_Position(0)
            ud.h_motor_Right.SetAbsMovePos(0,(pos_iniziale_Y+i*Value_step));
           
            output = ud.h_motor_Right.MoveAbsolute(0,1==0);
                                
            t1 = clock; 
            while(etime(clock,t1)<timeout) 
                s = ud.h_motor_Right.GetStatusBits_Bits(0);
                if (IsMoving(s) == 0)
                    break;
                end
                pause(1);
            end
           
pause(0.5);
        end % fine ciclo i (ho finito di scorrere anche le colonneY)

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% OPERAZIONI DI FINE SCANSIONE                                     %%
%  OBIETTIVO: TORNARE ALLA POSIZIONE INIZIALE, cioè in (DX,DY) nel  %%
%  sistema di riferimento della griglia:                            %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
        % Riportiamo il motore di sinistra alla posizione iniziale salvata
        % come Deault_X1 in modo da poter effetuare una seconda scansione 
        % Ciò accade quando entrambi i motori sono fermi.

        wait_stop(h_motor_Right)
        wait_stop(h_motor_Left)

        %Current_X = ud.h_motor_Left.GetPosition_Position(0)
        ud.h_motor_Left.SetAbsMovePos(0,pos_partenza_X1);
        output = ud.h_motor_Left.MoveAbsolute(0,1==0);

        t1 = clock; 
        while(etime(clock,t1)<timeout) 
            s = ud.h_motor_Left.GetStatusBits_Bits(0);
            if (IsMoving(s) == 0)
              break;
            end
             pause(1);
        end

        % Riportiamo il motore di destra alla posizione inizialesalvata
        % come Deault_X1 in modo da poter effetuare una seconda scansione
        % Ciò accade quando entrambi i motori sono fermi.
       
        wait_stop(h_motor_Right)
        wait_stop(h_motor_Left)

        %Current_Y = ud.h_motor_Right.GetPosition_Position(0)
        ud.h_motor_Right.SetAbsMovePos(0,pos_partenza_Y1);
        output = ud.h_motor_Right.MoveAbsolute(0,1==0);

        t1 = clock; 
        while(etime(clock,t1)<timeout) 
            s = ud.h_motor_Right.GetStatusBits_Bits(0);
            if (IsMoving(s) == 0)
              break;
            end
             pause(1);
        end             

        % copiamo il file temp.txt in un file con nome definito dall'utente
        filenamedefault = strcat('Data/',num2str(det_number),'Scan_',num2str(Value_dX*1000),'x',num2str(Value_dY*1000),'_',num2str(Value_step*1000),'um_step_',num2str(voltage),'volt_',num2str(current,'%E'),'A.txt')
        %[FileName,PathName] = uiputfile(filenamedefault,'Save data')
        %copyfile('Data/temp.txt', strcat(PathName,FileName));
        copyfile('Data/temp.txt', filenamedefault);

        
        formichiere='';
        save('Data/temp.txt', 'formichiere', '-ASCII'); 
        time=fix(clock);
        save('Data/temp2.txt', 'time', '-ASCII', '-append');
        

        end 
        
                [cuurent,voltage]= inizialize_keithley(0,R);

    I=figure(1)
    immagine=(imread('end.jpg'));
    g=imshow(immagine)
    h = uicontrol('Position',[20 20 200 40],'String','Continue',...
              'Callback','uiresume(gcbf)');
    disp('Close to continue');
    uiwait(gcf); 
    close(I)
        
        
    end %fine funzione Make_scan2 


end %% end of APT_interface function