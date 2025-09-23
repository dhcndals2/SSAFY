function quadratic_function(b, c)
    x = -10:0.1:10;

    a_values = linspace(-2, 2, 200);

    y_initial = a_values(1) * x.^2 + b*x + c;

    figure
    h = plot(x, y_initial, 'LineWidth', 2);


    grid on;
    xlabel('x');
    ylabel('y');

    for a = a_values
        y = a*x.^2 + b*x + c;

        set(h, 'YData', y);

        title(sprintf('y = %.2f*x^2 + %g*x + %g', a, b, c));

        pause(0.1);
    end
end
