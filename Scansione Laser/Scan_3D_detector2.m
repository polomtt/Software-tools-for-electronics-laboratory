function [ud_handle] =  Scan_3D_detector2
%% NOTE
%  1) motore sinistra -> asse x, motore destra -> asse y

global h_Ctrl;
%%%%%%%%%%%%%%%%%
%% Inizializza %%
%%%%%%%%%%%%%%%%%
    % apre una question dialog box
    button = questdlg('About to launch the APT window - do not run if another APT window is open.  Do you want to open the APT window?', ...
                  'Launch APT window', 'Yes', 'No', 'No');
    if isempty(button)
        return
    elseif length(button) == 2
        return
    end

    % Parametri
    ParamSet = 'FIRST_STEPS'; % Nome del setting gia'  inizializzato usando l'APT User program

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
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

%%%%%%%%%%%%%%%%%%%%%%%%
%% Configura i motori %%    %% MOTORE SINISTRA X;  MOTORE DESTRA Y;
%%%%%%%%%%%%%%%%%%%%%%%%
    [temp, num_motor] = h_Ctrl.GetNumHWUnits(6, 0);
    %controllo numero motori
    if num_motor ~= 2  
        fprintf(['Check number of motors (Found' num2str(num_motor) ')!\n']);
        return
    end

    % Ottengo il numero seriale del primo (index 0) e del secondo dispositivo (index1)
    [temp, SN_motor{1}] = h_Ctrl.GetHWSerialNum(6, 0, 0); 
    [temp, SN_motor{2}] = h_Ctrl.GetHWSerialNum(6, 1, 0); 
    SN_motor

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

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Crea pulsante per fermare APT %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    uicontrol(fig, 'Style', 'pushbutton', 'String', 'Stop APT interface',...
            'Position', [0 300 120 20],...
            'Callback',@Stop_APT_interface);        
    
    function Stop_APT_interface(~,event)
        APT_figure_delete_fcn(ud_handle);
    end



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Configurazione grafica dell'interfaccia di controllo utente %%
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
                'Position',[255 240 50 20], 'Callback', @step_Callback)  
            
    % String default step
    handle_Scan_options.step = uicontrol(fig, 'Style','edit',...
                'String','10',...
                'Position',[250 270 50 20], 'Callback', @step_Callback);  
            

    handle_Scan_options.btnRead =  uicontrol(fig, 'Style', 'pushbutton', 'String', 'Read values',...
                'Position', [350 300 120 20],...
                'Callback', @Prepare_scan);        

   
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

        Value_dX   = str2num(get(handle_Scan_options.dX,'String'))
        Value_dY   = str2num(get(handle_Scan_options.dY,'String'))
        Value_step = str2num(get(handle_Scan_options.step,'String'))
 
        if  (Value_dX<0)|(Value_dX>12000)
            questdlg('Put proper values', 'Warning', 'Ok','Ok');
        end

        Current_X = ud.h_motor_Left.GetPosition_Position(0); 
        Current_Y = ud.h_motor_Right.GetPosition_Position(0);
        
        if rem(Value_step,0.5)~=0
            questdlg('Make step value multiple to 0.5um', 'Warning', 'Ok','Ok');
        end
        
    end


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%SCALA TEMPI acquisizione

  
    %inizializzazione oscilloscopio
    %[deviceObj_r] = initialize_oscilloscope_Rob;

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        
%%%%%%%%%%%%%%%%%%%%%%%%%%       
%% Funzione Make_scan2  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%

         
%Creazione pulsante di avvio Make_scan2   
    
 
    
    uicontrol(fig, 'Style', 'pushbutton', 'String', 'Make scan 2',...
              'Position', [450 370 120 20],...
              'Callback', @Make_scan2);
            

          
          
          
          
          
          %implementazione        
 function Make_scan2(hObject, eventdata, handles)
        
  reply=0;      
              % controlla se la cartella Data esiste altrimenti la crea
        if exist('Data','dir')~=7 
            mkdir('Data');
        end        
        if exist('Data2/temp.txt','file') 
            delete('Data2/temp.txt');
        end        
        pause(1);  
%azzoro il file tempo
formichiere='';
save('Data/temp.txt', 'formichiere', '-ASCII');
 time=fix(clock);
 save('Data/temp2.txt', 'time', '-ASCII', '-append');
        

        
        
        %Calcola la matrice dimensione: divide dX e dY e step di 1000 in
        %modo da passare da decimetri di um (unita'  di misura dei motori) a millimetri
        
        Value_dX   = str2num(get(handle_Scan_options.dX,'String'))/1000;
        Value_dY   = str2num(get(handle_Scan_options.dY,'String'))/1000;
        Value_step = str2num(get(handle_Scan_options.step,'String'))/1000;
        
        time_scale=str2num(get(handle_Scan_options.time_scale,'String'))*10%% (10tacche perchè la get_wave vuole Horizontal_Time_Per_Record)
        
        %L'annomontare di step scannarizzati e' doppio rispetto a quanto
        %richiesto dall'utente: infatti il punto zero (punto d'inizio dei
        %motori) e' ora considerato al centro di una matrice di dimensioni
        %2*dX 2*dY con stesso step.
        %Arrotondo (round) all'intero piu' vicino in modo da evitare numeri
        %virgola mobile 
        
        m = round(Value_dY/Value_step)*2+1; %non ha senso far così
        n = round(Value_dX/Value_step)*2+1;
        
        %gcf = gestione figura corrente
        %gca = gestione asse corrente
        get(gcf);    
        set(gca, 'Units','points','View', [-120 60],...
        'Position',[550,200,350,320],... %%[left bottom width height]
        'XLim',[0,Value_dX*m],'YLim',[0,Value_dY*n], 'ZLim', [0, 100],... %%xlim e y lim tengono gia conto di DX e DY raddoppiati
        'PlotBoxAspectRatio',[1,1,1],'FontSize',8,...
        'Box', 'on'); %, 'CameraTarget', [-120, 60]);
    
        
        %Mi sposto in (N,M)=(1,1) ossia in (x',y')=(-DX,-DY) prendendo come
        %riferimento assi cartesiani con l'origine posizionata in (DX,DY)
        %della griglia (assumendo assi cartesiani X e Y con origine nell'angolo in basso a sinistra della griglia creata)
        ud.h_motor_Left.SetRelMoveDist(0, Value_dX/(-1));       
        output = ud.h_motor_Left.MoveRelative(0, true)
        ud.h_motor_Right.SetRelMoveDist(0, Value_dY/(-1));       
        output = ud.h_motor_Right.MoveRelative(0, true)
%aaa=2    
       
        Mean_value = zeros(m,n);%crea matrice mxn di zeri
        Mean_value_area = zeros(m,n);%crea matrice mxn di zeri
        Mean_value_max = zeros(m,n);%crea matrice mxn di zeri  (Ch1)
        Mean_value_max2 = zeros(m,n);%crea matrice mxn di zeri (Ch3)

 scrsz = get(0,'ScreenSize')
% 
% figure('Position',[1 scrsz(4)/2 scrsz(3)/2 scrsz(4)/2])
% 
%         subplot(2,4,3) % first subplot
%         fig = bar3(Mean_value);         %crea grafico 3d barre              
%         set(gca,'ZTick',[0:5:100]);     %gestione dell'asse della figura corrente     

%aaa=3          
        % m - corrisponde a asse Y
        % n - corrisponde a asse X

close
I=figure(1)
% immagine=(imread('dopo.jpg'));
% g=imshow(immagine)
% h = uicontrol('Position',[20 20 200 40],'String','Continue',...
%               'Callback','uiresume(gcbf)');
% disp('Close to continue');
% uiwait(gcf); 
% close(I)

        % [wave,assex]=get_wave2(deviceObj_r,'noise',time_scale);
 
I=figure(1)
% immagine=(imread('prima.jpg'));
% g=imshow(immagine)
% h = uicontrol('Position',[20 20 200 40],'String','Continue',...
%               'Callback','uiresume(gcbf)');
% disp('Close to continue');
uiwait(gcf); 
close(I)

        
        for i=1:m
            for j=1:n % scorriamo lungo l'asse delle X
                    % acquisisce i dati
                    nomefile=strcat('scan_Y-',num2str(i),'scan_X-',num2str(j),'.txt');
                    
%aaa=3000                  

                    % [Mean_value_area(i,j),Mean_value_max(i,j),Mean_value_max2(i,j),waveform_new]= get_wave_NO_Noise_sub(deviceObj_r,nomefile,time_scale);
                    %Mean_value_area(i,j)= get_wave(deviceObj_r,nomefile,time_scale, wave);

                    
%                     temporary_solution(1) = j;
% %aaa=300
%                     temporary_solution(2) = i;
%                     temporary_solution(3) = Mean_value_area(i,j);
%                     temporary_solution(4) = Mean_value_max(i,j);
%                     temporary_solution(5) = Mean_value_max2(i,j);
%                     %save2( i, j, 'temp.txt','y')
% 
% 
%                     save('Data/temp.txt', 'temporary_solution', '-ASCII', '-append');
%                     save('Data/temp2.txt', 'temporary_solution', '-ASCII', '-append');
% %aaa=3
% %temporary_solution
% %bbb=3
%                     % Creiamo il grafico dei dati con barre di colore
%                     % corrispondente alla loro altezza usando dubbed
%                     % Mean_value_mod array
% 
%                        subplot(2,4,2) % first subplot
%                        Mean_value_mod = Mean_value_area;
%                     %COMMENTATO PER CONFIGURARE SCALA VOLTAGGI
%                      plot_handle = bar3(Mean_value_mod);  
           
                    
                        for k = 1:n                         % ciclo che va riga per riga
                        zdata = ones(6*m,4);                % crea un array vuoto di colormap
                        counter = 1;

                            for l = 0:6:(6*m-6)             % ciclo da 0 a (m-1)*6 con step 6 
                                % vogliamo cambiare colormap 
                                % zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
                                % prendiamo  6 righe di zdata e assegniamo loro Mean_value_mod
                                counter = counter+1;
                            end
                                % set(plot_handle(k),'Cdata',zdata);  % Cdata e' responsabile del colore della mappa
                        end
                        
                     title('area')
                       
                    subplot(2,4,3) % first subplot
                    % Mean_value_mod = Mean_value_max;
                    %COMMENTATO PER CONFIGURARE SCALA VOLTAGGI
                     % plot_handle = bar3(Mean_value_mod);  
           
                    
                        for k = 1:n                         % ciclo che va riga per riga
                        zdata = ones(6*m,4);                % crea un array vuoto di colormap
                        counter = 1;

                            for l = 0:6:(6*m-6)             % ciclo da 0 a (m-1)*6 con step 6 
                                % vogliamo cambiare colormap 
                                % zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
                                % prendiamo  6 righe di zdata e assegniamo loro Mean_value_mod
                                counter = counter+1;
                            end
                           
                     
                            % set(plot_handle(k),'Cdata',zdata);  % Cdata e' responsabile del colore della mappa
                        end
                        
                        
                         title('Max')  
                         
                         
                         subplot(2,4,4) % first subplot
                    % Mean_value_mod = Mean_value_max2;
                    % %COMMENTATO PER CONFIGURARE SCALA VOLTAGGI
                    % plot_handle = bar3(Mean_value_mod);  
           
                    
                        for k = 1:n                         % ciclo che va riga per riga
                        zdata = ones(6*m,4);                % crea un array vuoto di colormap
                        counter = 1;

                            for l = 0:6:(6*m-6)             % ciclo da 0 a (m-1)*6 con step 6 
                                % vogliamo cambiare colormap 
                                % zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
                                % prendiamo  6 righe di zdata e assegniamo loro Mean_value_mod
                                counter = counter+1;
                            end
                           
                     
                            % set(plot_handle(k),'Cdata',zdata);  % Cdata e' responsabile del colore della mappa
                        end
                        
                        
                         title('Max2')  
             
                        
                        % proseguiamo al prossimo punto d'acquisizione sulla
                    % stessa riga quando entrambi i motori sono fermi
                  
                       % subplot(2,4,7) % first subplot
                       % plot(assex,waveform_new)
                       % title('istantaneo') 
                       % subplot(2,4,8) % first subplot
                       % plot(assex,wave)
                       % title('reference') 
                    
                    
                    
                    wait_stop(h_motor_Right)
                    wait_stop(h_motor_Left)
                    %pause(1); %pausa di un secondo
                    ud.h_motor_Left.SetRelMoveDist(0, Value_step); %muovo il motore di sinistra (asse X) di uno step verso destra  
                    output = ud.h_motor_Left.MoveRelative(0, true);
%aaa=8      
            end  %fine ciclo j (ho finito di scorrere tutta la riga X)
%aaa=4            
            % quando siamo a fine riga, attendiamo che entrambi i motori siano fermi 
            %dopodiche' torniamo al punto N=1 della riga successiva 
            wait_stop(h_motor_Right)
            wait_stop(h_motor_Left)

            ud.h_motor_Left.SetRelMoveDist(0, Value_step*(n)*(-1)); %riporto il motore di sinistra a inizio riga
            output = ud.h_motor_Left.MoveRelative(0, true); 
            
            %attendo nuovamente entrambi i motori siano fermi
            wait_stop(h_motor_Right)
            wait_stop(h_motor_Left)

            % muoviamo il motore di destra (Asse y) sulla riga successiva
            ud.h_motor_Right.SetRelMoveDist(0, Value_step)
            output = ud.h_motor_Right.MoveRelative(0, true)
                 
        end % fine ciclo i (ho finito di scorrere pure le colonneY)
        
%aaa=5        
    %%%%%%%OPERAZIONI DI FINE SCANSIONE%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % OBIETTIVO: TORNARE ALLA POSIZIONE INIZIALE, cioè in (DX,DY) nel    %%
    %   sistema di riferimento della griglia:                            %%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
    % Riportiamo il motore di sinistra alla posizione iniziale: muoviamo il motore sinistro
    % (asseX) in avanti di Value_dx, poichè terminata la scansione di una riga ci riportiamo all'inizio della riga successiva.
    %Ciò accade quando entrambi i motori sono fermi.
    
    wait_stop(h_motor_Right)
    wait_stop(h_motor_Left)
    
    ud.h_motor_Left.SetRelMoveDist(0, Value_dX);
    output = ud.h_motor_Left.MoveRelative(0, true);

    
   
    %Riportiamo il motore di destra alla posizione iniziale: muoviamo il
    %motore destro(asseY) indietro di un valore DY , quando entrambi i motori sono fermi
    % TO DO: tenere d'occhio per possibili errori di reset della Y
    
    wait_stop(h_motor_Right)
    wait_stop(h_motor_Left)

    ud.h_motor_Right.SetRelMoveDist(0, Value_dY*(-1));
    output = ud.h_motor_Right.MoveRelative(0, true);
    
    
%aaa=6

    % copiamo il file temp.txt in un file con nome definito dall'utente
    filenamedefault = strcat('Data/Scan_',num2str(Value_dX*1000),'x',num2str(Value_dY*1000),'_',num2str(Value_step*1000),'um_step.txt')
    [FileName,PathName] = uiputfile(filenamedefault,'Save data')
    copyfile('Data/temp.txt', strcat(PathName,FileName));

    end
    
    
%%
end %% end of APT_interface function