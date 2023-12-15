function [] = sub_plot_matrice (dx,dy,step,indirizzo,lambda,volt)

%addpath(genpath('C:\Users\Marie Curie\Desktop\STUDENTI\GianMarco\laser_max_dpo3034 - MATH - slow signal\sensor(50x50)\irraggiato\definitive'))
load(indirizzo);
imax = (dx/step)+1;
jmax = (dy/step)+1;
temp = dlmread(indirizzo);
value = temp(:,3);
%maxi=max(value);
maxi=0.02;
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
y=0:step:dx;

imagesc(x,y,matrix)
colorbar

 xlabel('x [\mum]','FontName','Times New Roman','FontSize',14);%,'FontWeight','bold')
 ylabel('y [\mum]','FontName','Times New Roman','FontSize',14);
combinedStr = ['Laser scan at ',lambda,' nm', ' at ', volt]
 title(combinedStr,'FontName','Times','FontSize',20,'FontWeight','bold')
