clc; close all

Tamb = 25;
HR = 50;
Tin = 32.8421;
q = 6;
Tout = 21.3105;

lb_x = 20;
ub_x = 90;

model_data_path = "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_andasol_gaussian_cascade.mat";
N = 1000;

tic

inner_fun = @(wwct) wct_residual(wwct, Tamb, HR, Tin, q, Tout, model_data_path);

elapsed_time = [];
best_fval = [];
N=100:100:1000;
for i=1:length(N)
    % X = lb_x + (ub_x - lb_x) .* rand(N(i), 1);
    X = linspace(lb_x, ub_x, N(i))';
    fvals = inner_fun(X);
    [best_val, idx] = min(fvals);
    best_x = X(idx,:)
    
    elapsed_time = [elapsed_time, toc];
    best_fval = [best_fval, best_val];
    fprintf('Found solution in %.4f seconds for N=%d\n', elapsed_time(i), N(i))
end
figure
scatter(X, fvals)
figure
plot(N, elapsed_time)
hold on
plot(N, best_fval)

function residual = wct_residual(wwct, Tamb, HR, Tin, q, Tout, model_data_path)
    Twct_out = wct_model_data(Tamb, HR, Tin, q, wwct, ...
        model_data_path=model_data_path, ...
        silence_warnings=true, ...
        raise_error_on_invalid_inputs=false, ...
        n_wct=1);
    
    residual = abs(Tout - Twct_out);
end
