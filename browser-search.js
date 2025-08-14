import puppeteer from 'puppeteer';

async function searchGoogle() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({ 
    headless: false, // Set to false to see the browser
    defaultViewport: null,
    args: ['--start-maximized']
  });
  
  const page = await browser.newPage();
  
  console.log('Navigating to Google...');
  await page.goto('https://www.google.com');
  
  console.log('Browser opened and Google loaded successfully!');
  
  // Keep the browser open for 30 seconds so you can see it
  setTimeout(async () => {
    console.log('Closing browser...');
    await browser.close();
  }, 30000);
}

searchGoogle().catch(console.error);