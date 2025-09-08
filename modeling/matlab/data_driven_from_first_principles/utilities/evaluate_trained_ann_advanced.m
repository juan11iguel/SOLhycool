%% Functions
function y = evaluate_trained_ann_advanced(x, ann, varargin)
    iP = inputParser;

    addParameter(iP, 'configuration_type',  "simple", @(x)validateattributes(x, {'string'},{'scalartext'}))

    parse(iP,varargin{:})

    configuration_type  = iP.Results.configuration_type;

    if strcmp(configuration_type, "simple")

        x_n = (x-ann.media_in)./ann.desviacion_in;
        y_n = ann.net(x_n');
        y = y_n .* ann.desviacion_out' + ann.media_out';

    elseif strcmp(configuration_type, "cascade")
        y = zeros(length(ann), length(x));

        % First output
        x_n = (x-ann{1}.media_in)./ann{1}.desviacion_in;
        y_n = ann{1}.net(x_n');
        y(1, :) = y_n .* ann{1}.desviacion_out' + ann{1}.media_out';

        for i=2:length(ann)
            x_n = [x_n, y_n'];
            y_n = ann{i}.net(x_n');
            y(i, :) = y_n .* ann{i}.desviacion_out' + ann{i}.media_out';
        end


    else
        error('unkown configuration_type argument')
    end


end