# Working
DONE run tests
DONE basic CLI usage
DONE basic web usage

how does it work
	rooftop
	balcony
	community
see if accurate
	understand the parts
better UI / can validate

# Fixes
* simplify
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
* claude default front end plug in
* want to use the playwright and LLM testing / verification of the website like I did in avird_2026
* I love the assumptions and the more details. I love the sources. However I think there needs to be the quick summary explanations shown (those look good that you have) but on mouse over / explain more need more detail. Like the "Share of your usage the subscription is sized to cover" like for someone new to community solar that's rough

* need an actual name for the site
* move header here for "every number is xyz, to bottom / side

# To do
* https://www.maine.gov/energy/electricity-prices was updated on 7/1
* with batteries with some of the mixed things
    * what combinations make sense?
        * stand alone batteries, rooftop solar, balcony solar
        * batteries with balcony
        * batteries with rooftop
* agent native
* feedback from users into the self improvement loop
* links to learning about / resources for understanding
* for CMP, the peak versus not peak usage part
* more research DER batters and using peak versus non-peak
* confirm how NPV is being used and if is this is the ideal calculation versus IRR or years until return
* I think the pricing on batteries isn't great. just one articla on Tesla powerwall
* NEB article is form 2024 and might not be accurate now

# Backlog
* MCP / way for other agents to access the tool and data
* leasing / non purchase for batteries and rooftop solar and what that means return wise
* power purchase agreements
* add more states
* be able to validate with mroe power bill examples
* commercial
* regular updates of sources
    * like https://www.maine.gov/energy/electricity-prices was updated on 7/1 . how to periodically check for key things?
* regular tidying up of repo

# Done