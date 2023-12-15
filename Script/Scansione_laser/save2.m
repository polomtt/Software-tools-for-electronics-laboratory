function save2= save2( x, y, filenamedafault,append)
filename=strcat(pwd,'\Data\',filenamedafault)
fzy= [x;y];
%plot(x,y)
%apre il file
if append=='y'
[fid msg]=fopen(filename, 'at'); %filename deve contenere il percorso
else
    [fid msg]=fopen(filename, 'wt'); %filename deve contenere il percorso
end
%se il file e` stato aperto con successo...
if(fid>0)
%scrive il vettore a su file
cont=fprintf(fid,'%6.2E %19.8E\n',fzy);
%informa l'utente dell'avvenuta scrittura
%disp([num2str(cont) 'written byte ...']);
%chiude il file
fclose(fid);
else %il file non e` stato aperto..
    disp(msg);
end