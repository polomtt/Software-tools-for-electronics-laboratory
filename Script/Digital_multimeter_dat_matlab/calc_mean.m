function [mean_qty, std_dev_qty] = calc_mean(qty_series)
    
    % baseline = 0;
    % 
    % % slice dei primi 10 elementi
    % if length(qty_series) >= 10
    %     slice = qty_series(1:10);
    %     baseline = mean(slice);
    % else
    %     mean_qty=0; 
    %     std_dev_qty=0;
    %     return;
    % end


    %seleziono e calcolo la media dei valori superiori alla baseline
    v_el_qty = [];  % vettore vuoto

    for i = 1:length(qty_series)
        if qty_series(i) > (0.5*max(qty_series))
            v_el_qty(end+1) = qty_series(i);
        end
    end

    mean_qty=mean(v_el_qty); 
    std_dev_qty=std(v_el_qty);

end


