
function [] = sub_plot_matrice_color_maps_R (dx,dy,step,indirizzo)
%addpath(genpath('C:\Users\Marie Curie\Desktop\STUDENTI\GianMarco\laser_max_dpo3034 - MATH - slow signal\sensor(80x80)'))
load(indirizzo);
imax = (dx/step)+1;
jmax = (dy/step)+1;
temp = dlmread(indirizzo);
value = temp(:,4);

display(max(value));
maxi=max(value);
%maxi= 0.3192;
%value=value/maxi;
k = 1;
matrix = zeros(imax,jmax);

for i = 1:imax
    for j = 1:jmax
        matrix(i,j) = value(k);
        k = k+1;
    end
end

figure();
x=0:step:dx;
y=0:step:dy;

imagesc(x,y,matrix)
%caxis([0 1])
colorbar

%volt = input('Volt');
 xlabel('x [\mum]','FontName','Times New Roman','FontSize',14);%,'FontWeight','bold')
 ylabel('y [\mum]','FontName','Times New Roman','FontSize',14);
combinedStr = ['Laser scan at 25 V ']
 title(combinedStr,'FontName','Times','FontSize',20,'FontWeight','bold')
end
 
%sub_plot_matrice (65,65,5,'Scan_65x65_5um_step(100v_20dg)2')
