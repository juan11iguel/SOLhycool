function error = calculo_w_dc(w_fan,Tout_ref, Tamb, q, Tin)
    
    try
        [Tout, ~] = dc_model_PSA(Tamb, Tin, q, w_fan);
    catch ME
        if strcmp(ME.identifier, 'WCT_model:invalid_input') || strcmp(ME.identifier, 'DC_model:invalid_input')
%             if contains(ME.message, 'Tin')
                % Water recirculating from outlet of DC to WCT is colder
                % than minimum evaluated temperature at WCT

                Tout=1e6;
%             end
        else 
            throw(ME)
        end
    end
    

 error = abs(Tout_ref - Tout);