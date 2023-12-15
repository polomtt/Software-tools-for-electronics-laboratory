Input = 'Data/2E/Misure/Scan_70x45_5um_step_2E_6V(1e-9).txt';

fid=fopen(Input);
data = textscan(fid, '%f %f %f %n')
fclose(fid);
row = data{2};
column = data{1};
mean_1  = data{4};

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
        
[m,n] = size(mean_matrix);


Mean_value_mod = mean_matrix;
figure;
plot_handle = bar3(Mean_value_mod);
for k = 1:n %% this is a cycle which goes row by row
zdata = ones(6*m,4); %% create an empty array of colormap
counter = 1;
    for l = 0:6:(6*m-6) % a cycle from 0 to (m-1)*6 with step 6 
        %% now we want to change colormap, we take 
        zdata(l+1:l+6,:) = Mean_value_mod(counter,k); 
        %% take 6 rows of zdata and assign to them
        %% Mean_value_mod
        counter = counter+1;
    end
    set(plot_handle(k),'Cdata',zdata); %%Cdata is responsible for the color map
end
                    