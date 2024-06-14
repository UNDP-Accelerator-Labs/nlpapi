import { ReportHandler } from 'web-vitals';

const reportWebVitals = (onPerfEntry?: ReportHandler) => {
  if (onPerfEntry !== undefined && onPerfEntry instanceof Function) {
    import('web-vitals').then((args) => {
      const { getCLS, getFID, getFCP, getLCP, getTTFB } = args;
      getCLS(onPerfEntry);
      getFID(onPerfEntry);
      getFCP(onPerfEntry);
      getLCP(onPerfEntry);
      getTTFB(onPerfEntry);
    });
  }
};

export default reportWebVitals;
