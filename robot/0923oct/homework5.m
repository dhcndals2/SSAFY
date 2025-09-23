clc;
clear;
close all;

x=linspace(0,2*pi,100);

h=plot(x,sin(x));
axis([0,2*pi,-1,1])

for k= 1:100
  y=sin(x-0.1*k);
  set(h,'YData',y);
  pause(0.1);
end



x = linspace(-2, 2, 50);
y = linspace(-2, 2, 50);
[X, Y] = meshgrid(x, y);

Z = sin(X) .* cos(Y);
h = surf(X, Y, Z);


axis([-2 2 -2 2 -1 1]);
title('3D Animation of a Surface Wave');
xlabel('x');
ylabel('y');
zlabel('z');

for k = 1:150
    t = k * 0.1;

    Z_new = sin(X + t) .* cos(Y);

    set(h, 'ZData', Z_new);

    pause(0.1);
end
