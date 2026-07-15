# Working
* TEST have the actual options compared side by side as built up or a button for this
* TEST when you click on a default option it doesn't work if the LLM is down. why?

* validate updated version
    DONE run tests pytest tests
    DONE basic web usage python -m http.server --directory web 8000     # then visit http://localhost:8000
    LLM usage
    explore the none community solar options
    other notes from below
    Questions
        is there not a venv on this?
        is the usage correct? no un venv mentioned?

# Fixes


# To do

* wiki updates
    * research the length of battery storage, 10 years seems too short
        * started in the wiki
    * more research DER batters and using peak versus non-pea
        * see wiki results
    * review updated wiki, see if any fixes need to be put into this
    * for CMP, the peak versus not peak usage part
    * I think the pricing on batteries isn't great. just one articla on Tesla powerwall
    * NEB article is form 2024 and might not be accurate now
    * https://www.maine.gov/energy/electricity-prices was updated on 7/1

* plan this out:
    * i'm not a huge fan of the layout, color scheme, text blobs etc. get a few different ideas for this
    * other  maybe quick fixes ideas
        * disclaimer as POC
            add this part to the bottom of the page and have a disclaimer that this is a proof of concept "Ask a plain question, get a fact-checkable answer. Every number below is a labeled, editable, sourced assumption — never a black box."
        * when editing the options, have it turn back into text. Maybe carry that text down like what is being shown with the rate of return stuff

    * feedback from users into the self improvement loop
    * Railway deploy
    * MCP / way for other agents to access the tool and data

    Let's plan out the rest of the things I want to finish up before I close out this POC:
        * I am not a huge fan of the layout, color scheme and many of the text blobs. Let's try 3 different layouts and I can see what sticks. This still seems too busy, too many different font sizes, bold / italics, colors etc. Seems somehow too busy and yet when flourishes or touches are added that are useful/needed them seem ugly.
        * Let's add a disclaimer at the bottom of the page that this is a POC.
        * remove this part "Ask a plain question, get a fact-checkable answer. Every number below is a labeled, editable, sourced assumption — never a black box."
        * when editing the options, have it turn back into text. Maybe carry that text down like what is being shown with the rate of return stuff
            * Is there a way to then kind of cache this so don't need the LLM to interpret?
        * Railway deploy
        * feedback from users into a self improvement loop (we'll have to talk about this more)
        * Deploy this as an MCP or other tool that agents can get access to the data and the process








# Backlog

* leasing / non purchase for batteries and rooftop solar and what that means return wise
* power purchase agreements
* add more states
* be able to validate with mroe power bill examples
* commercial
* regular updates of sources
    * like https://www.maine.gov/energy/electricity-prices was updated on 7/1 . how to periodically check for key things?
* regular tidying up of repo
* need to thing through how I present the financial argument
    * for sure non interest and discount payback return
    * maybe "if I had invested this money, what percent return would I need for equivalent savings"
    * thinking maybe a click through and show all the financial parts to it, NPV, IRR etc.
    * first one
* links to learning about / resources for understanding
* agent native
* ug, this website is stil way too fucking busy

# Done
* DONE better metric ideas:
    * bold the payback in years
    * have the NPV value rounded to the nearest dollar and be NPV: $x (7% discount rate)

* DONE with batteries with some of the mixed things
    * what combinations make sense?
        * stand alone batteries, rooftop solar, balcony solar
        * batteries with balcony
        * batteries with rooftop
* DONE initial review
    DONE run tests
    DONE basic CLI usage
    DONE basic web usage

    DONE how does it work
        rooftop
        balcony
        community
    DONE see if accurate
        understand the parts
    DONE better UI / can validate


* DONE last fix broke it, can't see the actual value now

* DONE balcony solar
    * change "balcony kit" to balcony solar.
    * how does this work "Annual production per kW (Maine)" when you adjust the size of the array?
    * explain what this means? $400.00 upfront · payback 3.1 yr · NPV $1,493.51 (solar wins at 7%)



* DONE more fixes
    * The README.md is not helpful. Like this website, in order to use the full text box, needs the agent thing to run which is not mentioned. Move all the .cli crap to some progressive disclosure doc, just one line and usage is needed in the readme

    * DONE this web page is oddly laid out. theres the ask button, then some text, then some options that can be opened or not, then the result, then more options below. When refining options below the affect on the price is hard to see because you have to scroll so far down. WHy not lay it out better? Result at top and it floats down with you and you can see it adjust as you change things.

    * DONE move this up and give an example. This should be below the "Ask" box. Also make it monthly / annual and wouldn't which provider matter as well. ALso provide an example. Like 'x kwh per month and CMP' :
        Want a tighter estimate? The most valuable thing you could tell us: your annual kWh usage (it's in your bill's usage history) — it replaces the bill→usage estimate with the real number.

    * DONE THere's too muhc goin on with teh default page. Have the refine stuff be hidden on initial page load and unless they expand it. WHen they do expand it have the full thing stuff with the option pricing then all that stuff down below

    * DONE Was this really redone with the front end plug in and playwright?
    * DONE Chagne the language in the footer:
        Defaults are values sourced from this repo <SET REPO LINK>. Edit any to fit your situation.
        Anything tagged unsourced — pending research should not be treated as established fact.
        Code available here <SET REPO LINK>






    
* DONE simplify
    * just a text box, default to "What savings would I get with community solar when my bill is $150 a month?"
        * Langgraph graph with agent deciding the routing
        * if agent is down or spending cap reached then default to the all box / click method
        * have a few more examples that can be clicked on for sample text
    * new prompt idea for more info that can refine the estimate
    * have an explanation of what the source is when you expand
    * no drop down, and no buttons to click across the top. default to community solar with average monthly rate
    * then button for refine with the boxes and can go strictly to it, when user clicks run this becomes new texts tatement on the top
        * no drop down for the types, just buttons that can be toggled with these combinations:
            * stand alone batteries, rooftop solar, balcony solar
            * batteries with balcony
            * batteries with rooftop
* DONE claude default front end plug in
* DONE want to use the playwright and LLM testing / verification of the website like I did in avird_2026
* DONE I love the assumptions and the more details. I love the sources. However I think there needs to be the quick summary explanations shown (those look good that you have) but on mouse over / explain more need more detail. Like the "Share of your usage the subscription is sized to cover" like for someone new to community solar that's rough

* DONE need an actual name for the site
