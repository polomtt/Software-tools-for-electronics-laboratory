function [] = sub_plot_matrice (dx,dy,step,indirizzo)

%addpath(genpath('C:\Users\Ennio\Documents\MATLAB\Data'))
load(indirizzo);
imax = (2*dx/step)+1;
jmax = (2*dy/step)+1;
temp = dlmread(indirizzo);
value = temp(:,4);
k = 1;
matrix = zeros(imax,jmax);

for i = 1:imax
    for j = 1:jmax
        matrix(i,j) = value(k);
        k = k+1;
    end
end

%figure();
h = bar3(matrix);
title(indirizzo,'Interpreter','none');

numBars = size(matrix,1);
numSets = size(matrix,2);

for w = 1:numSets
    zdata = ones(6*numBars,4);
    l = 1;
    for r = 0:6:(6*numBars-6)
        zdata(r+1:r+6,:) = matrix(l,w);
        l = l+1;
    end
    set(h(w),'Cdata',zdata)
end

xlabel('righe - scansione orizzontale');
ylabel('colonne - scansione verticale');

%MAT = matrix;
