% Source: https://es.mathworks.com/matlabcentral/answers/1670649-bar-plot-with-a-hatched-fill-pattern#answer_916574

y = 0.5*randn(3,5)+2; % a simplified example
hp = bar(y);
cm = colororder; % or replace with the desired colormap
hatchfill2(hp(1),'single','HatchAngle',0,'hatchcolor',cm(1,:));
hatchfill2(hp(2),'cross','HatchAngle',45,'hatchcolor',cm(2,:));
hatchfill2(hp(3),'single','HatchAngle',45,'hatchcolor',cm(3,:));
hatchfill2(hp(4),'single','HatchAngle',-45,'hatchcolor',cm(4,:));
hatchfill2(hp(5),'cross','HatchAngle',30,'hatchcolor',cm(5,:));
for b = 1:numel(hp)
    hp(b).FaceColor = 'none';
end