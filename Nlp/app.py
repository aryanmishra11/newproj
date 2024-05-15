from dotenv import load_dotenv
import streamlit as st
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage,HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import google.generativeai as genai
import mysql.connector
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
    You are a Data Analyst at a company. You are interacting with a user who is asking you questions about the company's database. Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into accout.
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



def is_valid(user_query,db):
    
    def get_schemas(_):
        return db.get_table_info()
    
    prompt=f"""you are a SQL expert you can tell if the question asked by the user in natural language is related to the Database or not given i provide you the database schema and the user question you have to respond if the question asked by the user is relevant to the database schema, if it is not related to the databse simply respond with a string NOT_RELATED only the string NOT_RELATED no backticks or any special charachters if it is related to my database respond with RELATED string only you can assume that if in user question database word is there or table word is there or any other word that resembles from any field of SQL it is Valid and you should return RELATED otherwise return NOT_RELATED also if there is word in general in the user query return NOT_RELATED and if the word database is written it should return RELATED
    <SCHEMA>{get_schemas}</SCHEMA>
    Question: {user_query}
    example: how are you
    response: NOT_RELATED
    example:What is the average age of females in the USA in general?
    response:NOT_RELATED
    example:What is the average age of females in the USA in my database?
    response:RELATED
    example: What do you do
    response: NOT_RELATED
    example: how many tables are there in my database
    response: RELATED
    example: how many person are not male in my database
    response:RELATED
    """
    
    
    model = genai.GenerativeModel("gemini-pro")
    response=model.generate_content([prompt])
    return response.text
    
def get_response(user_query:str, db:SQLDatabase,chat_history:list):
    sql_chain=get_sql_chain(db)
    

    template="""
    You are a Data Analyst at a company.you can generate responses other than database also and You are interacting with a user who is asking you questions about the company's database.using all the tables in the schema and using all the information required from the database , Based on the table schema below,question,sql query, and sql response, write a natural language response as an output. use the whole database schema and give accurate results the output should contain only the response not like Natural Lanaguage Response: and then response only the response
    <SCHEMA>{schema}</SCHEMA>
    example:how many tables are there in my database
    response: there are 3 tables in the database 
    
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
    
    st.text_input("Host",value="sql6.freesqldatabase.com",key="Host")
    st.text_input("Port",value="3306",key="Port")
    st.text_input("User",value="sql6705444",key="User")
    st.text_input("Password",type="password",value="NqySep38km",key="Password")
    st.text_input("Database",value="sql6705444",key="Database")
    
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
        
        if is_valid(user_query,SQLDatabase)=="NOT_RELATED":
            model = genai.GenerativeModel("gemini-pro")
            response=model.generate_content([user_query])
            st.markdown(response.text)
            st.session_state.chat_history.append(AIMessage(content=response.text))
        else:   
            response=get_response(user_query,st.session_state.db,st.session_state.chat_history)
            st.markdown(response)
            st.session_state.chat_history.append(AIMessage(content=response))