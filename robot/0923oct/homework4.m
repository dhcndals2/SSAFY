clc;
clear;
close all;


x=-10:0.1:10;
y=x.^2+2*x+1;

figure
plot(x,y);
title('Graph of y = x^2+2x+1');
xlabel('x');
ylabel('y');

grid on
hold off;



x=-pi:0.1:pi;
y1=sin(x);
y2=cos(x);
y3=tan(x);
figure
plot(x,y1,'-r','LineWidth',1);
hold on;
plot(x,y2,'-blue','LineWidth',1);
plot(x,y3,'-g','LineWidth',1);

title('Comparison of sin(x), cos(x), and tan(x)');
xlabel('x');
ylabel('y');
legend('sin(x)','cos(x)','tan(x)');

grid on
hold off;

x=-5:0.1:5;
y=-5:0.1:5;

[X, Y] = meshgrid(x, y);
Z = sin(sqrt(X.^2 + Y.^2));

figure
surf(X, Y, Z);
title('3D Surface Plot of z = sin(sqrt(x^2+y^2))');
xlabel('x');
ylabel('y');
zlabel('z');

grid on

