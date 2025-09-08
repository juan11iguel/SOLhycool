function fig = represent_result(data, output_vars_idx, input_vars_idx, ...
                          output_vars_sensor_types, varargin)

    iP = inputParser;

    addParameter(iP, 'configuration_type',  "simple", @isstring)
    addParameter(iP, 'alternative', "ann", @isstring)
    addOptional(iP, 'titles', ["Outlet water temperature", "Water consumption"])
    addParameter(iP, 'save_figure', false, @islogical)
    addParameter(iP, 'figure_path', "", @isstring)
    addParameter(iP, 'figure_name', @isstring)
    addParameter(iP, 'additional_text', "", @isstring)
    addParameter(iP, 'test_legend_str', "Tests", @isstring)


    addOptional(iP, 'net_wct', nan)
    addOptional(iP, 'tr_wct', nan)

    % addOptional(iP, 'gpr_tout', nan)
    % addOptional(iP, 'gpr_mlost', nan)
    addOptional(iP, 'model_wct', cell(0))
    
    addOptional(iP, 'data_val', table)

    parse(iP,varargin{:})

    configuration_type = iP.Results.configuration_type;
    alternative = iP.Results.alternative;
    save_figure = iP.Results.save_figure;
    figure_path = iP.Results.figure_path;
    figure_name = iP.Results.figure_name;
    data_val = iP.Results.data_val;
    additional_text = iP.Results.additional_text;
    test_legend_str = iP.Results.test_legend_str;

    net_wct = iP.Results.net_wct;
    tr_wct = iP.Results.tr_wct;

    model_wct = iP.Results.model_wct;

    fig = figure('Units', 'normalized', 'Position', [0.1, 0.1, 0.3, 0.7]);
    
    % Only works if one output is used
    color_ann = '#5AA9A2';
    color_poppe = "#E77C8D";
    colors = [color_ann, color_poppe];
    var_names = ["T_{w,o}", "Q_{w,lost}"];
    titles = iP.Results.titles;
    units = ["ºC", "l/h"];
    
    %     tl = tiledlayout(2,2);
    tl = tiledlayout("flow");
    for idx = 1:length(output_vars_idx)

        if ~isempty(data_val)
            out_ref_test = table2array(data_val(:,output_vars_idx(idx)));
            out_ref_train = table2array(data(:,output_vars_idx(idx)));
            out_ref = [out_ref_test; out_ref_train];

            x_train = table2array(data(:, input_vars_idx));
            x_val = table2array(data_val(:, input_vars_idx));

        else
            x_train = table2array(data(tr_wct.trainInd, input_vars_idx));
            x_val = table2array(data(tr_wct.testInd, input_vars_idx));
            
            out_ref = table2array(data(:,output_vars_idx(idx)));
            out_ref_test = out_ref(tr_wct.testInd,output_vars_idx(idx));
            out_ref_train = out_ref(tr_wct.trainInd,output_vars_idx(idx));
        end


        out_train = evaluate_model(x_train, alternative, model_wct);
        out_test  = evaluate_model(x_val, alternative, model_wct);
        % if strcmp(alternative, "ann")
        %     out_train = evaluate_model(x_train, model_wct);
        %     out_te
        %     % out_train = evaluate_trained_ann_advanced(x_train , net_wct, configuration_type=configuration_type);
        %     % out_test  = evaluate_trained_ann_advanced(x_val, net_wct, configuration_type=configuration_type);
        % 
        % elseif strcmp(alternative, "gaussian") || strcmp(alternative, "random_forest")
        % 
        %     out_train = zeros(height(data), 2);
        %     [out_train(:,1), ~, ~] = predict(model_wct{1}, x_train);
        %     [out_train(:,2), ~, ~] = predict(model_wct{2}, [x_train, out_train(:,1)]);
        % 
        %     out_test = zeros(height(data_val), 2);
        %     [out_test(:,1), ~, ~] = predict(model_wct{1}, x_val);
        %     [out_test(:,2), ~, ~] = predict(model_wct{2}, [x_val, out_test(:,1)]);
        % 
        %     out_test = out_test';
        %     out_train = out_train';
        % 
        % elseif strcmp(alternative, "gradient_boosting")
        % 
        %     out_train = zeros(height(data), 2);
        %     out_train(:,1) = predict(model_wct{1}, x_train);
        %     out_train(:,2) = predict(model_wct{2}, [x_train, out_train(:,1)]);
        % 
        %     out_test = zeros(height(data_val), 2);
        %     out_test(:,1) = predict(model_wct{1}, x_val);
        %     out_test(:,2) = predict(model_wct{2}, [x_val, out_test(:,1)]);
        % 
        %     out_test = out_test';
        %     out_train = out_train';
        % 
        % elseif strcmp(alternative, "radial_basis")
        %     if iscell(model_wct)
        %         % Cascade
        %         out_train = zeros(height(data), 2);
        %         out_train(:,1) = sim(model_wct{1}, x_train')';
        %         out_train(:,2) = sim(model_wct{2}, [x_train, out_train(:,1)]')';
        % 
        %         out_test = zeros(height(data_val), 2);
        %         out_test(:,1) = sim(model_wct{1}, x_val')';
        %         out_test(:,2) = sim(model_wct{2}, [x_val, out_test(:,1)]')';
        % 
        %         % Not the smartest kid in town
        %         out_test = out_test';
        %         out_train = out_train';
        %     else
        %         % Simple
        %         out_train = sim(model_wct, x_train');
        %         out_test = sim(model_wct, x_val');
        %     end
        % 
        % else
        %     throw(MException('represent_result:unkown_alternative', 'Unsupported alternative %s', alternative))
        % end
    
        % RMSE = sqrt(immse(out_ref_test, out_test(idx,:)'));
        RMSE_tr = sqrt(mse(out_ref_train, out_train(:, idx)));
        RMSE_test = sqrt(mse(out_ref_test, out_test(:, idx)));
        
        % Calculate uncertainty
        uncertainty = calculate_uncertainty(out_ref, output_vars_sensor_types(idx));
        lower_bound = out_ref - uncertainty;
        upper_bound = out_ref + uncertainty;
        
        ax = nexttile; hold(ax, 'on');
        % Plot the uncertainty bounds
        shadedplot(ax, out_ref', upper_bound', lower_bound', '#ffbe6f', '#3d3846');
    
        plot(out_ref, out_ref, 'Color','k', 'HandleVisibility','on')%'LineWidth',2,, 'Color', color_poppe)
        plot(out_ref_train, out_train(:, idx), 'x', 'MarkerEdgeColor', colors(2), ...
            'LineWidth',2, 'HandleVisibility','on')
        plot(out_ref_test, out_test(:, idx), 'o', 'MarkerEdgeColor', colors(1), ...
            'LineWidth',2, 'MarkerFaceColor', colors(1), 'HandleVisibility','on')

        
        % plot(out_ref, out_ref-uncertainty, ':', 'Color', 'k', 'LineWidth', 1)
        % plot(out_ref, out_ref+uncertainty, ':', 'Color', 'k', 'LineWidth', 1)
        % fill([out_ref; flipud(out_ref)], [upper_bound; flipud(lower_bound)], 'c', 'FaceAlpha', 0.3, 'EdgeColor', 'none');
        
        xlim(ax, [0.9*min(out_ref), 1.05*max(out_ref)])
        ylim(ax, [0.9*min(lower_bound), 1.1*max(upper_bound)])
    
        set(ax,'XGrid','on','YGrid','on');
        ax.FontSize=14;
            
        [t, s] = title( titles(idx), sprintf('RMSE (%s): Train = %.1f, Evaluation = %.1f %s', units(idx), RMSE_tr, RMSE_test, additional_text) );

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

    lg = legend(ax, 'Perfect fit', 'Train', test_legend_str, 'Uncertainty', Orientation='horizontal'); %Location='southoutside');
    lg.Layout.Tile = 'south';

    % lg = legend(ax, 'Ajuste ideal', 'Pts test', 'Pts entrenamiento', ...
    %     Orientation='horizontal', Location='northoutside'); %Location='southoutside');
    % lg.Layout.Tile = 'south';
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