function [area]= integrale_area(x,y)

xx=abs(x);
yy=abs(y);  


area_a = trapz(xx,yy);
%area_b = trapz(xxx,yyy)
area=abs(area_a)

%   plot (xx,yy)
%    hold on
%    plot (xxx,yyy)
%    
   
   
   