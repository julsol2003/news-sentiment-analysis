from flask import Flask, render_template, request, redirect
from newspaper import Source, Article
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from urllib.parse import urlparse
from collections import defaultdict
import datetime
import threading

app = Flask(__name__)
app.secret_key = 'super_secret_key' 
analyzer = SentimentIntensityAnalyzer()

user_sources = defaultdict(lambda: {
    "articles": [],
    "domain": "",
    "last_update": None,
    "sentiment": {"positive": 0, "negative": 0, "neutral": 0}
})

lock = threading.Lock()

def extract_domain(url):
    parsed = urlparse(url)
    return parsed.netloc or parsed.path

def fetch_and_analyze(url):
    with lock:
        print(f"Rozpoczynam analizę dla: {url}")
        try:
            source = Source(url, memoize_articles=False)
            source.build()
            print(f"Pobrano {len(source.articles)} artykułów z {url}")

            if not source.articles:
                print(f"Brak artykułów dla {url}")
                return

            new_articles = []
            added_articles = 0
            for article in source.articles:
                if added_articles < 20: 
                    try:
                        article.download()
                        article.parse()
                        title_words = article.title.lower().split()

                        #ignorowanie artykułów z krótkim tytułem z news
                        if "news" in title_words and len(title_words) <= 4:
                            print(f"Pominięto artykuł: {article.title}")
                            continue

                        #analiza sentymentu
                        sentiment = analyzer.polarity_scores(article.text)
                        sentiment_label = (
                            "positive" if sentiment['compound'] >= 0.05
                            else "negative" if sentiment['compound'] <= -0.05
                            else "neutral"
                        )

                        new_articles.append({
                            "title": article.title,
                            "url": article.url,
                            "sentiment": sentiment_label,
                            "date": article.publish_date or datetime.datetime.now()
                        })
                        print(f"Dodano artykuł: {article.title}")
                        added_articles += 1

                    except Exception as e:
                        print(f"Błąd pobierania artykułu: {e}")

            user_sources[url]["articles"].extend(new_articles)
            user_sources[url]["domain"] = extract_domain(url)
            user_sources[url]["last_update"] = datetime.datetime.now()

            for article in new_articles:
                user_sources[url]["sentiment"][article["sentiment"]] += 1

            print(f"Aktualizacja zakończona")

        except Exception as e:
            print(f"Błąd analizy źródła {url}: {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        new_url = request.form.get('url').strip()
        print(f"Otrzymano URL: {new_url}")
        
        if new_url:
            fetch_and_analyze(new_url)
        
        return redirect('/')
    
    return render_template('index.html', sources=user_sources.items())


@app.route('/remove/<path:url>')
def remove_source(url):
    with lock:
        if url in user_sources:
            del user_sources[url]
    return redirect('/')

@app.route('/update_data', methods=['GET'])
def update_data():
    for url in list(user_sources.keys()):
        fetch_and_analyze(url)

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)