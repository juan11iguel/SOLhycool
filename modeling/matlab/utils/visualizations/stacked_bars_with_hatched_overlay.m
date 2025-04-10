
close all
addpath("hatchfill2_r8/")

% Data

% Stacked bars data. Should add to 100%
dc = [70, 56, 40];
wct = [30, 44, 60];
% Overlay bar over dc. Should be less or equal to dc
dc_wct = [30, 10, 5];

% Normalize to make the sum of each stack equal to 100%
total = dc + wct; 
dc = dc ./ total * 100;
wct = wct ./ total * 100;
dc_wct = dc_wct ./ total * 100;

% Colors for bars
dcColor = [0.2, 0.6, 0.8]; % Blue for dc
wctColor = [0.9, 0.6, 0.2]; % Orange for wct

% Create the stacked bar plot
figure;
hold on;

% Bar positions
x = 1:length(dc);

% Plot stacked bars
bar(x, [dc; wct]', 'stacked', 'EdgeColor', 'none', 'FaceColor', 'flat');

% Customize bar colors
hBars = get(gca, 'Children');
hBars(1).FaceColor = 'flat'; % WCT layer
hBars(1).CData = repmat(wctColor, length(x), 1);
hBars(2).FaceColor = 'flat'; % DC layer
hBars(2).CData = repmat(dcColor, length(x), 1);

% Overlay dashed-filled bars for dc_wct
for i = 1:length(dc)
    % Define the coordinates for the patch
    x0 = x(i) - 0.4; % Left edge of the bar
    width = 0.8; % Width of the bar
    y0 = dc(i) - dc_wct(i); % Bottom edge of the overlay
    height = dc_wct(i); % Height of the overlay
    
    % Define the vertices of the patch
    x_vertices = [x0, x0 + width, x0 + width, x0];
    y_vertices = [y0, y0, y0 + height, y0 + height];
    
    % Create the patch
    p = patch(x_vertices, y_vertices, 'w', 'EdgeColor', wctColor, ...
              'LineStyle', '--', 'LineWidth', 3, 'FaceColor', 'none');
    
    % Apply the hatch fill
    hatchfill2(p, 'single', 'HatchAngle', 45, 'hatchcolor', wctColor, 'HatchLineWidth', 2);
end

% Adjust axis
ylim([0, 100]);
xlabel('Categories');
ylabel('Percentage (%)');
xticks(x);
xticklabels({'A', 'B', 'C'}); % Customize x-axis labels
legend({'DC', 'WCT'}, 'Location', 'northwest');
title('Normalized Stacked Bar Plot with Hatched Overlay');

hold off;
