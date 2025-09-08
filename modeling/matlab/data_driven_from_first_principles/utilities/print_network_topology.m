function output_str = print_network_topology(net)
%PRINT_NETWORK_TOPOLOGY Summary of this function goes here
%   Detailed explanation goes here
% Iterate over layers
if ~iscell(net)
    net = {net};
end

output_str = '';
for idx=1:numel(net)
    for i = 1:numel(net{idx}.layers)
        output_str = [output_str, sprintf('%d', net{idx}.layers{i}.size)];
        if i < numel(net{idx}.layers)
            output_str = [output_str, '-'];
        end
    end
    if idx < numel(net)
        output_str = [output_str, ', '];
    end
end


end

