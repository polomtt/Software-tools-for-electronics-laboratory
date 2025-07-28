function SaveWave(time_vec,ch1_vec,ch2_vec,filename)
    % Function to save on a txt file a waveform
    vec_length = length(time_vec);
    str_file = strcat(filename,'.txt');
    fid = fopen(str_file, 'w');
    fprintf(fid,'time,ch1,ch2\n');
    for i=1:vec_length
        fprintf(fid,'%e,%f,%f\n',time_vec(i),ch1_vec(i),ch2_vec(i));
    end
    fclose(fid);
end