%% Script to run all examples
% Include here all examples to evaluate in order to test they run without
% errors

addpath(genpath("utils/"))
addpath(genpath("component_models/"))

n_examples = 5;

for fn_idx=1:n_examples
    filenames = [
        "test_model.m";
        "example_simple_combined_cooler_model.m";
        "example_extended_combined_cooler_model.m";
        "example_evaluate_operation.m";
        "example_fans_calculator.m"
    ];
    fprintf("Evaluating %s\n", filenames(fn_idx))
    run(filenames(fn_idx))
end

fprintf("All tests/examples run without errors\n")