function fig = regression_plot(data_val_test, data_val_mod, output_vars_idx, options)
    arguments
        data_val_test {istable}
        data_val_mod {istable}
        output_vars_idx {isvector}
        options.output_vars_sensor_types  {isvector} = []
        options.titles = []
        options.units = []
        options.save_figure = false
        options.figure_path = ""
        options.figure_name = "regression_plot"
        options.test_legend_str {isstring} = "Tests"
    end


    fig = figure('Units', 'normalized', 'Position', [0.1, 0.1, 0.3, 0.7]);
    
    % Only works if one output is used
    color_ann = '#5AA9A2';
    color_poppe = "#E77C8D";
    colors = [color_ann, color_poppe];
    if ~isempty(options.titles)
        titles = options.titles;
    else
        variable_names = string(data_val_test.Properties.VariableNames);
        titles = variable_names(output_vars_idx);
    end

    if ~isempty(options.units)
        units = options.units;
    else
        if ~isempty(options.output_vars_sensor_types)
            units = strings(1, length(options.output_vars_sensor_types));
            for i=1:length(options.output_vars_sensor_types)
                if strcmp(options.output_vars_sensor_types(i), "pt100")
                    units(i) = "ºC";
                else
                    units(i) = "m³/h";
                end
            end
        else
            units = strings(1,length(output_vars_idx));
        end
    end
    
    %     tl = tiledlayout(2,2);
    tl = tiledlayout("flow");
    for idx = 1:length(output_vars_idx)

        out_ref = table2array(data_val_test(:,output_vars_idx(idx)));
        out_mod  = table2array(data_val_mod(:,output_vars_idx(idx))); % evaluate_model(x_val, alternative, model_wct);

        % Calculate performance metric
        RMSE_test = rmse(out_ref, out_mod);
        
        % Calculate uncertainty
        if ~isempty(options.output_vars_sensor_types)
            uncertainty = calculate_uncertainty(out_ref, options.output_vars_sensor_types(idx));
        else
            uncertainty = 0;
        end
        lower_bound = out_ref - uncertainty;
        upper_bound = out_ref + uncertainty;
        
        ax = nexttile; hold(ax, 'on');
        % Plot the uncertainty bounds
        shadedplot(ax, out_ref', upper_bound', lower_bound', '#ffbe6f', '#3d3846');
    
        plot(out_ref, out_ref, 'Color','k', 'HandleVisibility','on')%'LineWidth',2,, 'Color', color_poppe)
        plot(out_ref, out_mod, 'o', 'MarkerEdgeColor', colors(1), ...
            'LineWidth',2, 'MarkerFaceColor', colors(1), 'HandleVisibility','on')

        xlim(ax, [0.9*min(out_ref), 1.05*max(out_ref)])
        ylim(ax, [0.9*min(lower_bound), 1.1*max(upper_bound)])
    
        set(ax,'XGrid','on','YGrid','on');
        ax.FontSize=14;
            
        [t, s] = title( titles(idx), sprintf('RMSE (%s): Test = %.1f', units(idx), RMSE_test),  'Interpreter', 'none' );

        t.FontSize = 14; t.FontWeight = "Bold";
        s.FontSize = 11;
    
        xlabel(sprintf('Experimental values (%s)', units(idx)), 'FontSize', 14)
        ylabel(sprintf('Predicted values (%s)', units(idx)), 'FontSize', 14)

        t.FontSize = 14; t.FontWeight = "Bold";
        s.FontSize = 11;

        % xlabel('Experimental values', 'FontSize', 14)
        % ylabel('Predicted values', 'FontSize', 14)
        xlabel(sprintf('Experimental values (%s)', units(idx)), 'FontSize', 14)
        ylabel(sprintf('Predicted values (%s)', units(idx)), 'FontSize', 14)

        set(ax, "TitleHorizontalAlignment", "left")

    end
    
    ha = area(ax, 0, 0);
    set(ha, 'FaceColor', "#ffbe6f");

    % xlabel(tl,'Valores experimentales', 'FontSize', 14)
    % ylabel(tl,'Valores estimados', 'Fontsize', 14)

    lg = legend(ax, 'Perfect fit', options.test_legend_str, 'Uncertainty', Orientation='horizontal'); %Location='southoutside');
    lg.Layout.Tile = 'south';

    % lg = legend(ax, 'Ajuste ideal', 'Pts test', 'Pts entrenamiento', ...
    %     Orientation='horizontal', Location='northoutside'); %Location='southoutside');
    % lg.Layout.Tile = 'south';
    box(lg, "off")

    if options.save_figure == true
        % figure_path = "resultados";
        % figure_name = "resultado_entrenamiento";
        
        saveas(gca, sprintf('%s/%s.png', options.figure_path, options.figure_name))
        saveas(gca, sprintf('%s/%s.eps', options.figure_path, options.figure_name), 'epsc')
        saveas(gca, sprintf('%s/%s.fig', options.figure_path, options.figure_name))

        fprintf("Saved figure in several formats in %s/%s\n", options.figure_path, options.figure_name)
    end


end
