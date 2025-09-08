function fig = represent_models_comparison(r, titles, save_figure, figure_path, figure_name)

    fig = figure('Units', 'normalized', 'Position', [0.1, 0.1, 0.35, 0.6]);

    color_ann = '#5AA9A2';
    color_poppe = "#E77C8D";
    colors = [color_ann, color_poppe, '#A291E1', '#C69255'];

    %     tl = tiledlayout(2,2);
    tl = tiledlayout("flow");

    for idx = 1:2
        
        if idx==1
            handle_visibility = 'on';
        else
            handle_visibility = 'off';
        end

        % Calculate uncertainty
        uncertainty = calculate_uncertainty(r.out_ref(:,idx), r.output_vars_sensor_types(idx));
        lower_bound = r.out_ref(:,idx) - uncertainty;
        upper_bound = r.out_ref(:,idx) + uncertainty;
        
        ax = nexttile; hold(ax, 'on');

        % Plot the uncertainty bounds
        shadedplot(ax, r.out_ref(:,idx)', upper_bound', lower_bound', '#ffbe6f', '#3d3846');
    
        % Plot the reference line
        plot(r.out_ref(:,idx), r.out_ref(:,idx), 'Color','k', 'HandleVisibility', handle_visibility)

        % Plot poppe results
        plot(r.out_ref(:,idx), r.out_poppe(:,idx), 'o', 'MarkerEdgeColor', colors(2), ...
            'LineWidth',2, 'MarkerFaceColor', colors(2), 'HandleVisibility',handle_visibility)
        
        % Plot ann results
        plot(r.out_ref(:,idx), r.out_ann(:,idx), 'o', 'MarkerEdgeColor', colors(1), ...
            'LineWidth',3, 'MarkerFaceColor', 'none', 'HandleVisibility',handle_visibility)

        % Plot a third result
        plot(r.out_ref(:,idx), r.out_other(:,idx), 's', 'MarkerEdgeColor', colors(3), ...
            'LineWidth',2, 'MarkerFaceColor', colors(3), 'HandleVisibility',handle_visibility)
    
        % Plot a fourth result
        plot(r.out_ref(:,idx), r.out_other2(:,idx), '^', 'MarkerEdgeColor', colors(4), ...
            'LineWidth',2, 'MarkerFaceColor', colors(4), 'HandleVisibility',handle_visibility)
    

        ha = area(ax, 0, 0);
        set(ha, 'FaceColor', "#ffbe6f");
        
        xlim(ax, [0.9*min(r.out_ref(:,idx)), 1.05*max(r.out_ref(:,idx))])
        ylim(ax, [0.9*min(lower_bound), 1.1*max(upper_bound)])
    
        set(ax,'XGrid','on','YGrid','on');
        ax.FontSize=14;
    
        [t, s] = title(titles(idx), ...
              sprintf('ANN (Cascade CF): RMSE=%.1f %s, R^2=%.2f, Poppe: RMSE=%.1f %s, R^2=%.2f', ...
                        r.rmse_ann(idx), r.units(idx), r.r2_ann(idx), ...
                        r.rmse_poppe(idx), r.units(idx), r.r2_poppe(idx)));

        t.FontSize = 14; t.FontWeight = "Bold";
        s.FontSize = 11;
    
        xlabel(sprintf('Experimental values (%s)', r.units(idx)), 'FontSize', 14)
        ylabel(sprintf('Predicted values (%s)', r.units(idx)), 'FontSize', 14)
    
    
        set(ax, "TitleHorizontalAlignment", "left")

        if idx==1
            lg = legend(ax, 'Perfect fit', 'Poppe', 'Cascade CF', 'MIMO Feedforward', 'MIMO Radial-basis', 'Uncertainty', Orientation='horizontal', NumColumns=3); %Location='southoutside');
            lg.Layout.Tile = 'south';
        end
    end
    
    % xlabel(tl,'Valores experimentales', 'FontSize', 14)
    % ylabel(tl,'Valores estimados', 'Fontsize', 14)
    
    
    box(lg, "off")
    
    if save_figure == true
        % figure_path = "resultados";
        % figure_name = "resultado_entrenamiento";
        
        saveas(gca, sprintf('%s/%s.png', figure_path, figure_name))
        saveas(gca, sprintf('%s/%s.eps', figure_path, figure_name), 'epsc')
        saveas(gca, sprintf('%s/%s.fig', figure_path, figure_name))

        fprintf("Saved figure in several formats in %s/%s\n", figure_path, figure_name)
    end

end