.PHONY: bot tetris both background

bot:
	python3 -X dev bot.py

tetris:
	python3 -X dev tetris.py

both:
	python3 -X dev tetris.py &
	python3 -X dev bot.py

background:
	nohup python3 bot.py </dev/null >/dev/null 2>/dev/null &

stop:
	killall -SIGINT python3
