function generate_partial_dataset(data_path, percentage, output_path)
%GENERATE_PARTIAL_DATASET Creates a subset of the data at a given percentage.
%
% Parameters:
%   data_path (1, :) char or string: Path to the input dataset
%   percentage (1,1) double {mustBePositive, mustBeLessThanOrEqual(percentage, 100)}: Percentage of data to include
%   output_path (1, :) char or string: Optional path for output (defaults to data_path)

    arguments
        data_path (1, :) {mustBeTextScalar}
        percentage (1,1) double {mustBePositive, mustBeLessThanOrEqual(percentage,100)}
        output_path (1, :) {mustBeTextScalar} = ""
    end

    % Determine output_path if not provided
    if output_path == ""
        [folder, ~, ~] = fileparts(data_path);
        if folder == ""
            folder = ".";
        end
        output_path = folder;
    end

     % Read data
    data=readtable(data_path);
    
    %% Selecciona número de puntos (cd) e indica a qué porcentaje corresponde (cd_p)
    
%     cd=23;    % 104, 92, 81, 69, 58, 46, 35, 23 , 12
    ratio=data.q./data.w_fan;
    cd = round(height(data)*percentage/100);
%     cd_p=20;  % 90,  80, 70, 60, 50, 40, 30, 20, 10
    
    for kk=1:length(cd)
       
        [ratio_max,index(1)]=max(ratio);
        data_sel(index(end))=1; % en este vector aquella posición con 1 significa que ese dato ha sido seleccionado
        [ratio_min,index(2)]=min(ratio);
        data_sel(index(end))=1; % en este vector aquella posición con 1 significa que ese dato ha sido seleccionado
        delta=(ratio_max-ratio_min)/(cd-1);
        
        
        vratio=ratio_min:delta:ratio_max;
        for k=1:length(vratio)-1
            [i,j]=find((ratio>vratio(k))&(ratio<=vratio(k+1)));
            if not(isempty(i))
                if length(i)>1
                    r=randi([1,length(i)]); %elijo número aleatorio entre los que hay
                    index(end+1)=i(r);
                else
                    index(end+1)=i(1);
                end;
                data_sel(index(end))=1; % en este vector aquella posición con 1 significa que ese dato ha sido seleccionado
            end;
        end;
        
        % si faltan valores para completar el %
        faltan=cd-sum(data_sel);
        if faltan>0
            for m=1:faltan
                i=find(data_sel<1);
                r=randi([1,length(i)]);
                index(end+1)=i(r);
                data_sel(index(end))=1;
            end;
        end;
        
        for k=1:length(index)
            data_new(k,:)=data(index(k),:);
    end;

    % Create output filename and save as CSV
    [~, name, ~] = fileparts(data_path);
    filename = sprintf('%s_%dp.csv', name, round(percentage));
    full_output_path = fullfile(output_path, filename);

    fprintf('Output saved to: %s\n', full_output_path);
    writetable(data_new, full_output_path )
    
    %%
    figure
    plot(ratio,'.')
    ratio_new=data_new.q./data_new.w_fan;
    hold on
    plot(ratio_new,'*r')
    legend('ratio inicial', 'ratio conjunto reducido')
    

end

