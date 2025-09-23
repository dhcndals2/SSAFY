function result=fibonacci_while_loop(n,threshold)

number = 1;
curnumber = 0;
beforenumber = 0;
b = false;
i = 1;
while (i <= n)
  if (i == 1)
    curnumber = 1;
    disp("1")
  elseif (i == 2)
    beforenumber = 1;
    disp("1")
  else
    number = curnumber + beforenumber;
    if (number > threshold && !b)
      b = true;
  disp(["i'm ",num2str(i),"st       ",num2str(number) , " over!!!!!!!"])
    end
    disp(number)
    beforenumber = curnumber;
    curnumber = number;
  end
  i = i + 1;
end
