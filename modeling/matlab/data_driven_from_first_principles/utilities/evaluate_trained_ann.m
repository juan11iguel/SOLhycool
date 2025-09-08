%% Functions
function y = evaluate_trained_ann(x, ann)

    x_n = (x-ann.media_in)./ann.desviacion_in;
    
    y_n = ann.net(x_n');

    y = y_n .* ann.desviacion_out' + ann.media_out';
end