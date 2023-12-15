% for i=1:max(data{1,1})
%     X()
% end
% X = 
% [X,Y,Z] = peaks(30);
% surfc(X,Y,Z)
% colormap jet
% axis([-3 3 -3 3 -10 5])
% dim_step=1e-5; % step a 10 um
% max(data{1,1})
% imagesc(row,column,data{1,3})
% colormap(jet(10))
% axis xy
% axis square


% colormap summer
% imagesc(spiral(100)), colorbar
% axis square
% axis off
% % set(gca, 'Clim',[1000 9000]) %setta i limiti del colore ColorLimits
% imagesc(10:10:300,1:0.1:10,spiral(100))
% title('Copper Shaft, Clim = [0 10000]')
% 

% crea matrice dati da rappresentare
    %introdurre valori della scansione
        step=1;
        %count_rows=righe(verticali)
        count_columns=size(row,1); %colonne sono in orizzontale da dx a sx
    
    
imagesc(-3:3,3:-1:0,prova), colorbar
axis square
title('Prova mia')

