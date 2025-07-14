%% Figuras simposium CEA
close all

% Condiciones de entrada
figure
s1=subplot(4,1,1);
bi1=bar([data.Tamb,data.HR]);
set(bi1(1),'DisplayName','T_{amb}',...
    'FaceColor',[0.850980392156863 0.325490196078431 0.0980392156862745],...
    'EdgeColor','none');
set(bi1(2),'DisplayName','HR','FaceColor',[0.8 0.8 0.8],...
    'EdgeColor',[0.650980392156863 0.650980392156863 0.650980392156863]);
set(s1,'XGrid','on','XTick',[1 2 3 4 5 6 7 8],'YGrid','on',...
    'YTick',[0 15 30 45 60] ,'YTickLabel',{'0','15','30','45','60'});
legend
% Create ylabel
ylabel({'T ambiente (ºC)','Humedad (%)'});
subplot(4,1,2)
bar(data.mv,'DisplayName','ms',...
    'FaceColor',[0.0745098039215686 0.623529411764706 1],...
    'EdgeColor',[0 0.447058823529412 0.741176470588235],...
    'BarWidth',0.4);
% Create ylabel
ylabel({'Flujo másico','vapor (kg/s)'});
ylim([100 350]);
xlim([0.5 8.5]);
grid

subplot(4,1,3)
bi2 = bar([data.qc,data.qdc,data.qwct],'EdgeColor','none');
set(bi2(1),'DisplayName','SC',...
    'FaceColor',[0.650980392156863 0.650980392156863 0.650980392156863]);
set(bi2(2),'DisplayName','ACHE',...
    'FaceColor',[0.466666666666667 0.674509803921569 0.188235294117647]);
set(bi2(3),'DisplayName','WCT',...
    'FaceColor',[0.494117647058824 0.184313725490196 0.556862745098039]);
% Create ylabel
ylabel({'Caudal  ','agua (m^3/h)'});
grid
legend
ylim([0 25])

subplot(4,1,4)
bi4=bar([data.wdc,data.wwct],'EdgeColor','none');
set(bi4(1),'DisplayName','ACHE',...
    'FaceColor',[0.466666666666667 0.674509803921569 0.188235294117647]);
set(bi4(2),'DisplayName','WCT',...
    'FaceColor',[0.494117647058824 0.184313725490196 0.556862745098039]);
legend
grid
ylim([0 100]);

% Create ylabel
ylabel({'Frecuencia','ventiladores (%)'});

% Create xlabel
xlabel({'Test'});
fontsize(16, "points")


%% Variables de salida
% Cálculo de errores
eT=0.03 + 0.005.*data.Tv; % suponiendo que es el mismo tipo de sensor que los del paper de Energy
eT_dc=0.03 + 0.005.*data.Tdc_out;
eT_wct=0.03 + 0.005.*data.Twct_out;
eT_sc=0.03 + 0.005.*data.Tcond;

FS=2; % full scale m3/h
FS_lh=2*1000; % full scale L/h
eMlost=ones(length(data.Cw),1).*(0.5*FS_lh)/100;


figure
subplot(3,1,1)
distribucion_hidraulica
xlim([0.5 8.5]);
subplot(3,1,2)
b2=bar([results.Cw],...
    'DisplayName','sim',...
    'FaceColor',[0.301960784313725 0.745098039215686 0.933333333333333],...
    'EdgeColor',[0 0.447058823529412 0.741176470588235],'BarWidth',0.3);
clear x2;
for i=1:size(b2,2)
  x2(i,:)=b2(i).XEndPoints;
end;
hold on
errorbar(x2(1,:)',data.Cw,eMlost,'MarkerSize',2,...
    'MarkerFaceColor',[0.149019607843137 0.149019607843137 0.149019607843137],...
    'Marker','o',...
    'LineStyle','none',...
    'Color',[0.149019607843137 0.149019607843137 0.149019607843137]);
xlim([0.5 8.5]);
ylim([0 250]);
grid
legend('sim','exp')
ylabel(['Consumo   ';'agua (L/h)']);
title('Salidas')

subplot(3,1,3)
bar1=bar([results.Tdc_out, results.Twct_out, results.Tv],'EdgeColor','none');
set(bar1(1),'DisplayName','ACHE',...
    'FaceColor',dcColor);
set(bar1(2),'DisplayName','WCT',...
    'FaceColor',wctColor);
set(bar1(3),'DisplayName','SC',...
    'FaceColor',[0.650980392156863 0.650980392156863 0.650980392156863],...
    'EdgeColor',[0.650980392156863 0.650980392156863 0.650980392156863]);

clear x;
for i=1:size(bar1,2)
  x(i,:)=bar1(i).XEndPoints;
end;
hold on
errorbar(x(1,:)',data.Tdc_out,eT_dc,'DisplayName','exp',...
    'MarkerSize',2,...
    'Marker','o',...
    'LineStyle','none','MarkerFaceColor',[0.349019607843137 0.509803921568627 0.141176470588235],...
    'Color',[0.27843137254902 0.411764705882353 0.109803921568627]);
    
errorbar(x(2,:)',data.Twct_out,eT_wct,'DisplayName','exp',...
    'MarkerSize',2,...
    'Marker','o',...
   'LineStyle','none','MarkerFaceColor',[1 0 1],'Color',[1 0 1]);
eb = errorbar(x(3,:)',data.Tcond,eT_sc,'DisplayName','exp',...
    'MarkerSize',2,...
    'MarkerFaceColor',[0.149019607843137 0.149019607843137 0.149019607843137],...
    'Marker','o',...
    'LineStyle','none',...
    'Color',[0.149019607843137 0.149019607843137 0.149019607843137]);

grid
ylim([25 51]);
legend([bar1(1),bar1(2), bar1(3),eb],...
        'Orientation','horizontal', 'NumColumns',4);
ylabel(['Temperaturas';'(^oC)       ']);
xlabel('Test')
fontsize(16, "points")

%% Regression plot of temperatures
regression_plot(data, rearrangeTable(data, results), ...
    [2, 6, 10, 11, 12, 15, 16, 13], ...
    output_vars_sensor_types=repmat("pt100", 1, 7));
fontsize(16, "points")
