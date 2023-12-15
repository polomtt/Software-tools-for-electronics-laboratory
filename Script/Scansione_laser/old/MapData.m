function [] = MapData(input_data,step,my_title)
%MAPDATA Given the cell, the step value and a title shows and saves the
%        checkerboard plot of the data.
%   
%   input_data: cell data obtained from script Read_temp_file.m
%   step: step dimension
%   my_title: title of acquisition

% Find rows (vertical from right to left)
    num_rows=max(input_data{1,2});
% Find columns (horizontal bottom->up)
    num_columns=max(input_data{1,1});
    
% Create ValMatrix with inverted horizontal axis
    temp=zeros(num_columns,num_rows);      
    for i=1:size(input_data{1,1},1)
        temp(input_data{1,2}(i,1),input_data{1,1}(i,1))=(input_data{1,3}(i,1));
    end
    temp=temp';
    temp=flipdim(temp,2);
    save ('provar.dat',temp);
% Plot data as image
    figure1=figure
    colormap hsv
    imagesc(1:-1,(num_rows*step):(-num_rows*step),temp), colorbar
    axis square
    title(my_title);
% Save graph as png
    saveas(figure1,strcat(my_title,'.png'));
end
