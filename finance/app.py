import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date

from json import loads
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    money = db.execute("SELECT * FROM users WHERE id = ? ", session["user_id"])
    owned_cash = int(money[0]['cash'])
    rows = db.execute("SELECT * FROM purchase WHERE user_id = ?", session["user_id"])
    total = owned_cash
    for row in rows:
        look = lookup(row['symbol'])
        row['name'] = look['name']
        row['price'] = look['price']
        row['total'] = row['price'] * row['shares']

        # increment sum
        total += row['total']

        # convert price and total to usd format
        row['price'] = usd(row['price'])
        row['total'] = usd(row['total'])


    return render_template ("homepage.html", owned_cash=owned_cash, rows=rows, total=total)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        if not (query := lookup(symbol)):
            return apology("INVALID SYMBOL")
        # select row of the symbol in table purchase
        if not symbol in query["symbol"]:
            return apology("INVALID SYMBOL")
        # compare to inpup
        row = db.execute("SELECT shares FROM purchase WHERE user_id = ? AND symbol = ? ", session["user_id"], symbol)
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        # load price mutiply by shares than substact from cash
        cash = rows[0]["cash"]

        if row:
            shares = int(row[0]["shares"])
        else:
            return apology("Invalid")


        sharess = int(request.form.get("shares"))
        if sharess > shares:
            return apology ("Sorry you dont have too much shares")

        total = shares - sharess
        if total == 0:
            db.execute("DELETE FROM purchase WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

        price = query["price"] * sharess
        money = cash + price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", money, session["user_id"])
        db.execute("UPDATE purchase SET shares = ? WHERE user_id = ? AND symbol = ?", total, session["user_id"], symbol)
        db.execute("INSERT INTO history (user, symbol, shares, price, buy ) VALUES(?, ?, ?, ?, ?) ",session["user_id"], symbol, sharess, query["price"], False )

        # select row of the shares in the table purchase

        # caompare to input
        # than lookup to price
        flash("Sold!!!")
        return render_template("sell.html", row=row)
    else:
        return render_template("sell.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # check symbol if it typed or not and check symbol if it exist or not
        if not request.form.get("symbol") or not lookup(request.form.get("symbol")) != None:
            return apology("wrong name" ,403)
        symbol = request.form.get("symbol").upper()
        if not request.form.get("shares") or not int(request.form.get("shares")) > 0  :
            return apology("less then 0",403)
        shares = int(request.form.get("shares"))
        # check shares
        # select cash
        if not (query := lookup(symbol)):
            return apology("INVALID SYMBOL")


        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        # load price mutiply by shares than substact from cash
        cash = rows[0]["cash"]
        total_prices = query["price"] * shares
        if cash < total_prices :
            return apology("LOX NIE MA $$$")
        total = cash - total_prices

        db.execute("INSERT INTO purchase (user_id, symbol, shares, price) VALUES (?, ? ,? ,?)",session["user_id"], symbol, shares, query["price"] )

        db.execute("UPDATE users SET cash = ? WHERE id = ?", total, session["user_id"])
        db.execute("INSERT INTO history (user, symbol, shares, price, buy ) VALUES(?, ?, ?, ?, ?) ",session["user_id"], symbol, shares, query["price"], True )
        flash("Bought!!!")
        return redirect ("/")


    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():

    histories = db.execute("SELECT * FROM history WHERE user = ?",session["user_id"])
   # if histories[0]["buy"] = True:
    #    bou
    return render_template("history.html", histories=histories)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if not (quote := lookup(request.form.get("symbol"))):
            return apology("invalid symbol")
        return render_template("quoted.html",quote=quote )

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        username = request.form.get("username")
        if not username:
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        if not request.form.get("rpassword") == request.form.get("password"):
            return apology("Password not matched")
        if username in rows:
            return apology("already registered", 403)

        password = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)

        db.execute("INSERT INTO users(username, hash) VALUES(?,?)", username, password)


        return redirect("/login")

    else:
        return render_template("register.html")
