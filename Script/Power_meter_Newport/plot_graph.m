function plot_graph(time_serie,power_serie,xlim_fig,title_fig)
    plot(time_serie(:),power_serie(:),'o');
    xlabel('Time [s]');
    ylabel('Poewr [W]');
    title(title_fig)
    set(gca, 'Position', [0.12,0.12,xlim_fig,0.80])
end