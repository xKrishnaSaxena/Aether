from langchain_community.tools import DuckDuckGoSearchResults,DuckDuckGoSearchRun

search_results_tool=DuckDuckGoSearchResults(num_results=1)
search_results_tool2=DuckDuckGoSearchRun(num_results=1)
raw_results=search_results_tool.run("What is python in Programming")
raw_results2=search_results_tool2.run("What is python in Programming")
print(raw_results)
