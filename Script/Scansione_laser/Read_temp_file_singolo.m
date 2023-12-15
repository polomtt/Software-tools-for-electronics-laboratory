Input = 'Data/Scan_50x50_5um_step_1E_5V(1e-9).txt';

fid=fopen(Input);
data = textscan(fid, '%f %f %f %n')
fclose(fid);
row = data{2};
column = data{1};
mean_1  = data{3};

count = 1;
count_rows = 1;
flag_next_row = 0;


%% Calculate amount of the rows in the corresponding matrix

if length(row)>1  
    for i=1:length(row)-1
        if row(i) ~= row(i+1)
            count_rows = count_rows+1;
        end;
    end

    if row(length(row))~=row(length(row)-1)
        count_rows = count_rows+1;
    end

elseif length(row)==1
    count_rows = 1;
else 
    count_rows =0;
    
end


count_columns = 0;
if count_rows>1
    for i=1:count_rows
        for j=1:length(row)            
        if row(j)==i
            count_columns = count_columns + 1;
            mean_matrix(i, count_columns) = mean_1(j);  
        end
        end
    count_columns = 0;           
    end
end    
        
