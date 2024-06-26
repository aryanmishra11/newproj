from dotenv import load_dotenv
import streamlit as st
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage,HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import getpass
import os

if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("GOOGLE_API_KEY")
load_dotenv()

#CHAT Interactivity part: to pass in the chat history to our SQL Chain

if "chat_history" not in st.session_state:
    #we can initialize it empty but i will initialize it with a AI Message
    st.session_state.chat_history=[
        AIMessage(content="Hello! I'm a SQL assistant. Ask me anything about the database"),
    ]

def init_database(user:str,password:str,host:str,port:str,database:str)->SQLDatabase:
    db_uri=f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(db_uri)

    
def get_sql_chain(db):
    template="""
    You are a Data Analyst at a company. You are interactig with a user who is asking you questions about the company's database. Based on the table schema below, write a SQL query tat would answer the user's question. Take the conversation history into accout.
    <SCHEMA>{schema}</SCHEMA>
    
    Write only the SQL query and nothing else. Do not wrap the SQL Query in any other text, not even backticks,
    
    for example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP By ArtistId ORDER By track_count DESC LIMIT 3;
    Question:Name 10 artists
    SQL Query:SELECT Name FROM Artist LIMIT 10;
    
    Your turn:
    
    Question: {question}
    SQL Query:
    """
    
    prompt=ChatPromptTemplate.from_template(template)
    llm = ChatGoogleGenerativeAI(model="gemini-pro")
    
    def get_schema(_):
        return db.get_table_info()
    
    return(
        RunnablePassthrough.assign(schema=get_schema)
        |prompt
        |llm
        |StrOutputParser()
    )
    
    
def get_response(user_query:str, db:SQLDatabase,chat_history:list):
    sql_chain=get_sql_chain(db)
    
    template="""
    You are a Data Analyst at a company. You are interactig with a user who is asking you questions about the company's database. Based on the table schema below,question,sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History:{chat_history}
    SQL Query:<SQL>{query}</SQL>
    User question: {question}
    SQL Response:{response}
    """
    
    #we passs the sql chain in order to get query it is going to return some variables like query
    prompt=ChatPromptTemplate.from_template(template)
    llm = ChatGoogleGenerativeAI(model="gemini-pro")
    chain=(
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _:db.get_table_info(),
            response=lambda vars: db.run(vars["query"]),
        )
        |prompt
        |llm
        |StrOutputParser()
    )
    
    return chain.invoke({
        "question":user_query,
        "chat_history":chat_history,
    })

st.set_page_config(page_title="Chat with MYSQL",page_icon=":speech_balloon:")
st.title("Chat With MYSQL")

with st.sidebar:
    st.subheader("Settings")
    st.write("This is a single chat application using MYSQL. Connect to the Database and start chatting.")
    
    st.text_input("Host",value="localhost",key="Host")
    st.text_input("Port",value="3306",key="Port")
    st.text_input("User",value="root",key="User")
    st.text_input("Password",type="password",value="admin",key="Password")
    st.text_input("Database",value="chinook",key="Database")
    
    if st.button("Connect"):
        with st.spinner("Connecting to Database...."):
            db=init_database(
                st.session_state["User"],
                st.session_state["Password"],
                st.session_state["Host"],
                st.session_state["Port"],
                st.session_state["Database"]                
            )
            # saving the state of the 
            st.session_state.db=db
            st.success("Connected")

#for displaying the AI AND Human message from the session state chat history
for message in st.session_state.chat_history:
    if isinstance(message,AIMessage):
        with st.chat_message("AI"):
            st.markdown(message.content)
    elif isinstance(message,HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)     
            
#for storing the messages of AI and Human in history of user question
user_query=st.chat_input("Type a message...")

if user_query is not None and user_query.strip!="":
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    
    #displaying the message in the conver
    with st.chat_message("Human"):
        st.markdown(user_query)
    
    with st.chat_message("AI"):
        response=get_response(user_query,st.session_state.db,st.session_state.chat_history)
        st.markdown(response)
    
    st.session_state.chat_history.append(AIMessage(content=response))