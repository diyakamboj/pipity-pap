So, what the current situation is, we have OpenHands. What I did was, I took OpenHands, reorganized the directory, cut out all the coding elements, and made a very powerful agentic runtime. The problem was that, while I was moving stuff around, the imports, etc., were not set up correctly.

So what happened was, when I ended up fixing the MCP part of it and added the MCP marketplace, I evaluated the implementation, and it turned out that the MCP server was not connected to the main agentic chat runtime.

I just wanted to point that out because now that we’re going to go through and finish our skills implementation, the skills implementation is fully there. We’re using the OpenHands system, right? So it should already be there, right? The only thing that isn’t there is the skills library, and that should be really easy to add.

Do not add your own implementation for a skills library. Everything is hooked up properly; you probably just need to make a folder in one place and fill it up. That’s legitimately it.

For now, if you’re going to fill it up, fill it up with dummy skills, like some random MD files.

The biggest thing that could happen is that the actual skills implementation is not hooked up to the main runtime, right? Because I was moving stuff around, the imports are not properly there. So if that is the case, that should be the very first thing to check to make sure everything is connected properly.

I want you to do as many tests as possible. Check the entire one-to-one pipeline, check every aspect of it, run multiple tests, run it from the UI, run it from the backend, run it from this, run it from that, to make sure the entire skills implementation has the correct plumbing and the skills library is being loaded properly.

Next thing, we need an AI Search MCP. So our implementation is an MCP marketplace. Marketplace meaning that the MCPs that we’re going to add should be things we can find on the web. There are sites called MCP marketplaces, or there are GitHub repositories with MCP servers already there.

I want you to find the most trustworthy and best implementation of the current server. I don’t want to get something from some random person. If there’s something good, use that.

Make sure you get an MCP server for Azure AI Search, right? You can get that in there. And then another one for Cosmos DB.

And it’s going to be a—I think—I’m not sure. I don’t understand databases, so I thought we would RAG the data. I don’t know. We’re going to be picking up documents from the Cosmos DB database, right?

So, understanding what our agent needs to be doing, it should be able to pull up documents for completing actions like onboarding someone. So it’s your choice on whether it’s going to be Azure AI Search, a RAG implementation, or whether it’s just going to be a keyword search. I have no idea how that stuff works.

So just imagine there would be an implementation to pick up something, a bunch of PDF files, from Cosmos DB.

The next MCP server, and this is the most important, is that we need an MCP server that can edit files. It should be able to work with PDFs or stuff like that. It should probably be able to deal with documents like Word documents and PDFs.

The biggest thing to make sure of is that it does not rewrite the documents. If it’s a PDF, it should not convert the PDF to a Word document and edit it that way. That would probably ruin the entire document.

The best thing you want is something that can just go through a PDF and maybe fill in specific points. Or, if it’s a Word document, it could fill out only the parts that are needed and maintain the rest of the document. It’s filling it out like a human would. That way, it doesn’t ruin the document in any possible way.

We need an MCP server for that. If you can find the best implementation of that, please do. We cannot make this on our own.

These things are the biggest priority, right?

Create a whole architecture. If you use my voice thing, it’s just going to be paragraphs and explanations. It’s not going to be diagrams with bullet points, no. It’s so we can build background, so when I run my agent, it has an insane level of background.

It should basically—if you want, you can take the transcription I have and just repurpose it and tweak a few things. That’s all it should be. It shouldn’t be too complex. You’re not summarizing anything, you’re not shortening anything. Give as much detail as we can.

Include the part about how it’s the OpenHands directory, how everything was moved around, everything was changed. I changed the folder layout because I didn’t like it, so that meant we had to relayout and re-hook up the imports. Stuff was cut out.

You understand? Explain as much as you can. Tell about how detailed the skills are. Explain everything I said about the skills stuff so it has enough of an understanding to not ruin it, you know?

The whole point here is that whenever you’re implementing something, you should not change any architecture because the architecture already exists. You should only be using the existing architecture and just fixing things and adding stuff to it.

And everything should be tested end-to-end. Nothing should be added as a separate implementation. No. Have a whole background directory, a whole background directory about how everything should be tested end-to-end.

And test it through the UI.

The whole issue is that the actual chat system is not connecting to the MCP. So when the previous agent was testing the MCP separately, it was working. But when I tested it through the chat, it wasn’t working.

Stuff like that, you know what I mean?  
