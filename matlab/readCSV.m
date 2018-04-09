filename = 'test.csv';
data = csvread(filename,1);

t = data(2:end,1);
m = data(2:end,2:end);

y = mean(m,2);
err = std(m,[],2);

hold on
scatter(t,y)
errorbar(t(1:20:end), y(1:20:end), err(1:20:end), 'LineStyle','none');
hold off